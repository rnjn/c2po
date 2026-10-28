import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def select_files(manifest, categories):
    return [f for f in manifest["data_files"] if f["category"] in categories]


def download(entry, out_dir, session_key):
    target = out_dir / entry["filename"]
    if target.exists():
        print(f"skip {target} (exists)")
        return True
    headers = {"User-Agent": "Mozilla/5.0"}
    if session_key:
        headers["Cookie"] = f"sessionKey={session_key}"
    req = urllib.request.Request(entry["export_url"], headers=headers)
    part = target.with_suffix(target.suffix + ".part")
    try:
        with urllib.request.urlopen(req) as resp, open(part, "wb") as fh:
            while chunk := resp.read(1 << 20):
                fh.write(chunk)
    except urllib.error.HTTPError as e:
        part.unlink(missing_ok=True)
        print(f"FAIL {entry['filename']}: HTTP {e.code}", file=sys.stderr)
        return False
    with open(part, "rb") as fh:
        if fh.read(2) != b"PK":
            print(
                f"FAIL {entry['filename']}: not a zip (likely login page); kept {part}",
                file=sys.stderr,
            )
            return False
    part.rename(target)
    print(f"ok   {target} ({target.stat().st_size} bytes)")
    return True


def main(argv):
    if len(argv) < 2:
        print("usage: download_export.py MANIFEST [OUT_DIR] [CATEGORY ...]", file=sys.stderr)
        return 2
    manifest = json.loads(Path(argv[1]).read_text())
    out_dir = Path(argv[2]) if len(argv) > 2 else Path("archive")
    categories = set(argv[3:]) or {"conversations"}
    out_dir.mkdir(parents=True, exist_ok=True)
    session_key = os.environ.get("CLAUDE_SESSION_KEY")
    results = [download(e, out_dir, session_key) for e in select_files(manifest, categories)]
    return 0 if results and all(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
