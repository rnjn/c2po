import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT_PARENT = "00000000-0000-4000-8000-000000000000"
MAX_RESULT_CHARS = 3000
MAX_TITLE = 120
UNSAFE = re.compile(r'[/\\:*?"<>|#^\[\]]')
SENDERS = {"human": "🧑 User", "assistant": "🤖 Claude"}


def safe_title(name):
    cleaned = " ".join(UNSAFE.sub(" ", name or "").split())
    return cleaned[:MAX_TITLE].rstrip() or "Untitled"


def display_title(conv):
    if conv.get("name", "").strip():
        return conv["name"].strip()
    for m in conv.get("chat_messages", []):
        if m.get("sender") == "human":
            first = (m.get("text") or "").strip().splitlines()
            if first:
                return first[0][:60]
    return "Untitled"


def note_filename(conv):
    return f"{conv['created_at'][:10]} {safe_title(display_title(conv))}"


def active_branch(messages):
    if not messages:
        return []
    by_id = {m["uuid"]: m for m in messages}
    parents = {m.get("parent_message_uuid") for m in messages}
    leaves = [m for m in messages if m["uuid"] not in parents] or messages
    node = max(leaves, key=lambda m: m["created_at"])
    path = []
    while node and node["uuid"] not in {p["uuid"] for p in path}:
        path.append(node)
        node = by_id.get(node.get("parent_message_uuid"))
    return list(reversed(path))


def fence(body):
    runs = [len(r) for r in re.findall(r"`{3,}", body)]
    return "`" * max([3] + [r + 1 for r in runs])


def code_block(body, lang=""):
    f = fence(body)
    return f"{f}{lang}\n{body}\n{f}"


def callout(kind, title, body):
    lines = [f"> [!{kind}]- {title}"]
    lines += [f"> {line}" if line else ">" for line in body.splitlines()]
    return "\n".join(lines)


def truncate(s, limit=MAX_RESULT_CHARS):
    if len(s) <= limit:
        return s
    return s[:limit] + f"\n… [truncated {len(s) - limit} chars]"


def render_tool_input(inp):
    if not isinstance(inp, dict):
        return code_block(json.dumps(inp, indent=2, ensure_ascii=False), "json")
    simple = {k: v for k, v in inp.items() if not (isinstance(v, str) and "\n" in v)}
    parts = []
    if simple:
        parts.append(code_block(json.dumps(simple, indent=2, ensure_ascii=False), "json"))
    for k, v in inp.items():
        if k not in simple:
            parts.append(f"**{k}**\n{code_block(v, inp.get('language', ''))}")
    return "\n\n".join(parts)


def render_tool_result(block):
    parts = []
    for item in block.get("content") or []:
        if not isinstance(item, dict):
            parts.append(str(item))
        elif item.get("url"):
            parts.append(f"- [{item.get('title') or item['url']}]({item['url']})")
        elif item.get("text"):
            parts.append(code_block(truncate(item["text"])))
    return "\n".join(parts) or "_(empty)_"


def render_block(block):
    t = block.get("type")
    if t == "text":
        return block.get("text", "").strip()
    if t == "thinking":
        thought = (block.get("thinking") or "").strip()
        return callout("thinking", "Thinking", thought) if thought else ""
    if t == "tool_use":
        return callout("tool", f"🔧 {block.get('name')}", render_tool_input(block.get("input")))
    if t == "tool_result":
        return callout("result", f"📤 {block.get('name')} result", render_tool_result(block))
    if t in ("image", "document"):
        return f"> 📎 _{t} attached (file not included in export)_"
    if t == "injected_prompt_block":
        return ""
    return callout("note", f"Unsupported block: {t}", code_block(json.dumps(block, indent=2)))


def render_message(m):
    parts = [f"## {SENDERS.get(m.get('sender'), m.get('sender'))}"]
    for a in m.get("attachments") or []:
        content = a.get("extracted_content") or "_(no extracted content)_"
        parts.append(callout("attachment", f"📎 {a.get('file_name')}", content))
    attached = {a.get("file_name") for a in m.get("attachments") or []}
    for f in m.get("files") or []:
        if f.get("file_name") not in attached:
            parts.append(f"> 📎 _{f.get('file_name')} (file not included in export)_")
    for block in m.get("content") or []:
        rendered = render_block(block)
        if rendered:
            parts.append(rendered)
    return "\n\n".join(parts)


def render_conversation(conv):
    title = display_title(conv)
    branch = active_branch(conv.get("chat_messages", []))
    front = [
        "---",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        f"uuid: {conv['uuid']}",
        f"created: {conv['created_at'][:19]}",
        f"updated: {conv['updated_at'][:19]}",
        f"url: https://claude.ai/chat/{conv['uuid']}",
        f"messages: {len(branch)}",
        "tags:",
        "  - claude",
        "---",
    ]
    body = [f"# {title}"]
    if conv.get("summary"):
        body.append(callout("summary", "Summary", conv["summary"]).replace("]-", "]+", 1))
    body += [render_message(m) for m in branch]
    return "\n".join(front) + "\n" + "\n\n".join(body) + "\n"


def render_index(entries):
    by_month = defaultdict(list)
    for conv, name in entries:
        by_month[conv["created_at"][:7]].append((conv, name))
    out = ["# Claude Conversations", "", f"{len(entries)} conversations.", ""]
    for month in sorted(by_month, reverse=True):
        out.append(f"## {month}")
        for conv, name in sorted(by_month[month], key=lambda e: e[0]["created_at"], reverse=True):
            alias = re.sub(r"[|\[\]]", " ", display_title(conv))
            out.append(f"- [[{name}|{alias}]]")
        out.append("")
    return "\n".join(out)


def convert(src, out_dir):
    convs = json.loads(Path(src).read_text(encoding="utf-8"))
    convs = sorted((c for c in convs if c.get("chat_messages")), key=lambda c: c["created_at"])
    used = set()
    entries = []
    for conv in convs:
        name = note_filename(conv)
        if name.lower() in used:
            name = f"{name} {conv['uuid'][:8]}"
        used.add(name.lower())
        folder = Path(out_dir) / "conversations" / conv["created_at"][:4]
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{name}.md").write_text(render_conversation(conv), encoding="utf-8")
        entries.append((conv, name))
    (Path(out_dir) / "Claude Conversations.md").write_text(render_index(entries), encoding="utf-8")
    return len(entries)


def main(argv):
    if len(argv) != 3:
        print("usage: claude_to_md.py CONVERSATIONS_JSON OUT_DIR", file=sys.stderr)
        return 2
    print(f"wrote {convert(argv[1], argv[2])} notes to {argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
