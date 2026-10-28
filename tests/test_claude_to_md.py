import json

import claude_to_md as c

ROOT = c.ROOT_PARENT


def msg(uuid, parent, sender, created, content, **extra):
    return {
        "uuid": uuid,
        "parent_message_uuid": parent,
        "sender": sender,
        "created_at": created,
        "content": content,
        "attachments": extra.get("attachments", []),
        "files": extra.get("files", []),
    }


def text(t):
    return {"type": "text", "text": t}


def convo(**over):
    base = {
        "uuid": "abcd1234-0000-0000-0000-000000000000",
        "name": "Hello: World?",
        "summary": "",
        "created_at": "2025-05-19T09:12:25.491457Z",
        "updated_at": "2025-05-19T09:13:35.371191Z",
        "chat_messages": [
            msg("m1", ROOT, "human", "2025-05-19T09:12:27Z", [text("hi there")]),
            msg("m2", "m1", "assistant", "2025-05-19T09:12:30Z", [text("hello back")]),
        ],
    }
    base.update(over)
    return base


def test_safe_title_strips_obsidian_unsafe_chars():
    assert c.safe_title('a/b\\c:d*e?f"g<h>i|j#k^l[m]n') == "a b c d e f g h i j k l m n"


def test_safe_title_falls_back_and_truncates():
    assert c.safe_title("   ") == "Untitled"
    assert len(c.safe_title("x" * 300)) <= 120


def test_note_filename_has_date_prefix():
    assert c.note_filename(convo()) == "2025-05-19 Hello World"


def test_active_branch_follows_latest_leaf():
    messages = [
        msg("m1", ROOT, "human", "2025-01-01T00:00:01Z", [text("q")]),
        msg("a_old", "m1", "assistant", "2025-01-01T00:00:02Z", [text("old")]),
        msg("a_new", "m1", "assistant", "2025-01-01T00:00:05Z", [text("new")]),
        msg("m3", "a_new", "human", "2025-01-01T00:00:06Z", [text("more")]),
    ]
    assert [m["uuid"] for m in c.active_branch(messages)] == ["m1", "a_new", "m3"]


def test_active_branch_linear_keeps_order():
    messages = convo()["chat_messages"]
    assert [m["uuid"] for m in c.active_branch(messages)] == ["m1", "m2"]


def test_fence_longer_than_inner_backticks():
    assert c.fence("plain") == "```"
    assert c.fence("has ``` inside") == "````"


def test_callout_prefixes_every_line():
    out = c.callout("tool", "web_search", "line1\nline2")
    assert out == "> [!tool]- web_search\n> line1\n> line2"


def test_render_thinking_is_collapsed_callout():
    out = c.render_block({"type": "thinking", "thinking": "deep\nthoughts"})
    assert out.startswith("> [!thinking]- Thinking")
    assert "> deep" in out


def test_render_tool_use_shows_input_json():
    out = c.render_block({"type": "tool_use", "name": "web_search", "input": {"query": "x"}})
    assert "[!tool]- 🔧 web_search" in out
    assert '"query": "x"' in out


def test_render_tool_result_lists_web_results():
    block = {
        "type": "tool_result",
        "name": "web_search",
        "content": [{"type": "knowledge", "title": "T", "url": "https://e.com", "text": "body"}],
    }
    out = c.render_block(block)
    assert "[T](https://e.com)" in out


def test_render_tool_result_truncates_long_text():
    block = {
        "type": "tool_result",
        "name": "bash",
        "content": [{"type": "text", "text": "y" * 10000}],
    }
    out = c.render_block(block)
    assert "truncated" in out
    assert len(out) < 6000


def test_render_skips_injected_prompt():
    assert c.render_block({"type": "injected_prompt_block", "prompt": "date"}) == ""


def test_render_image_and_document_placeholders():
    assert "image" in c.render_block({"type": "image", "file_uuid": "u"})
    assert "document" in c.render_block({"type": "document", "file_uuid": "u"})


def test_render_message_includes_attachment():
    m = msg(
        "m1",
        ROOT,
        "human",
        "2025-01-01T00:00:00Z",
        [text("see file")],
        attachments=[{"file_name": "a.md", "extracted_content": "# Doc"}],
    )
    out = c.render_message(m)
    assert out.startswith("## 🧑 User")
    assert "[!attachment]- 📎 a.md" in out
    assert "> # Doc" in out


def test_render_conversation_frontmatter_and_body():
    out = c.render_conversation(convo())
    head, body = out.split("\n---\n", 1)
    assert head.startswith("---\n")
    assert 'title: "Hello: World?"' in head
    assert "uuid: abcd1234-0000-0000-0000-000000000000" in head
    assert "created: 2025-05-19T09:12:25" in head
    assert "url: https://claude.ai/chat/abcd1234-0000-0000-0000-000000000000" in head
    assert "messages: 2" in head
    assert "  - claude" in head
    assert "# Hello: World?" in body
    assert "## 🤖 Claude" in body
    assert "hello back" in body


def test_convert_writes_notes_index_and_dedupes(tmp_path):
    src = tmp_path / "conversations.json"
    dup = convo(uuid="ffff9999-0000-0000-0000-000000000000")
    empty = convo(uuid="eeee0000-0000-0000-0000-000000000000", chat_messages=[])
    src.write_text(json.dumps([convo(), dup, empty]))
    out = tmp_path / "vault"
    count = c.convert(src, out)
    assert count == 2
    notes = sorted(p.name for p in (out / "conversations" / "2025").iterdir())
    assert notes == ["2025-05-19 Hello World ffff9999.md", "2025-05-19 Hello World.md"]
    index = (out / "Claude Conversations.md").read_text()
    assert "## 2025-05" in index
    assert "[[2025-05-19 Hello World|Hello: World?]]" in index


def test_render_skips_empty_thinking():
    assert c.render_block({"type": "thinking", "thinking": "  "}) == ""
