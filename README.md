# Claude Conversation History → Obsidian

Converts a claude.ai data export into Markdown notes for viewing in [Obsidian](https://obsidian.md).

## Requirements

- [uv](https://docs.astral.sh/uv/) (installs Python and dependencies automatically)

```
uv sync
```

## Fresh import

1. **Request an export** on claude.ai: Settings → Privacy → Export data. You receive a `manifest-*.json` with download links (valid ~24h, may be single-use).
2. **Download `conversations-000.zip`**, either by opening its `export_url` from the manifest in your browser, or with the script:
   ```
   CLAUDE_SESSION_KEY='<sessionKey cookie>' uv run python -I tools/download_export.py ~/Downloads/manifest-*.json archive conversations
   ```
   The `sessionKey` value is under DevTools → Application → Cookies → `https://claude.ai`.
3. **Unzip it into `archive/`**:
   ```
   unzip -o archive/conversations-000.zip -d archive/conversations-000
   ```
   (If you downloaded via the browser, use `~/Downloads/conversations-000.zip` instead.)
4. **Convert**:
   ```
   uv run python -I tools/claude_to_md.py archive/conversations-000/conversations.json .
   ```
   Existing notes are overwritten, so re-running with a newer export is safe.
5. **Open in Obsidian**: "Open folder as vault" → this folder, and start from `Claude Conversations.md`.

## Output

```
Claude Conversations.md          index grouped by month, newest first
conversations/
  2025/2025-05-19 Some Title.md  one note per conversation
  2026/...
```

Each note has:

- **Frontmatter**: `title`, `uuid`, `created`, `updated`, `url` (link back to claude.ai), `messages`, and the `claude` tag
- `## 🧑 User` / `## 🤖 Claude` headings per turn
- Collapsed callouts for thinking, tool calls, tool results and file text included in the export
- Tool results cut at 3,000 characters; web search results keep their list of links
- Only the latest version of edited or regenerated chats, as on claude.ai

Not included: uploaded images and PDFs (the export only says a file was attached), and chats with no messages.

## Development

```
uv run pytest
uv run ruff check . && uv run ruff format .
```

Your conversation data (`archive/`, `conversations/`, `Claude Conversations.md`) and `.obsidian/` are git-ignored; only code is committed.
