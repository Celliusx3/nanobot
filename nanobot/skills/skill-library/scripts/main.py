#!/usr/bin/env python3
"""Skill library — browse and install skills from a GitHub repo.

Usage:
    main.py list    <owner/repo>
    main.py read    <owner/repo> <slug>
    main.py install <owner/repo> <slug>
"""

import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

WORKSPACE = Path(os.environ.get("NANOBOT_WORKSPACE", Path.home() / ".nanobot" / "workspace"))


def api(endpoint: str) -> any:
    """Call GitHub API and return parsed JSON."""
    url = f"https://api.github.com/{endpoint}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.environ.get("GH_TOKEN", "")
    if token:
        headers["Authorization"] = f"token {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def download_dir(repo: str, path: str, dest: Path) -> None:
    """Recursively download a directory from GitHub to a local path."""
    dest.mkdir(parents=True, exist_ok=True)
    for item in api(f"repos/{repo}/contents/{path}"):
        target = dest / item["name"]
        if item["type"] == "file":
            data = api(f"repos/{repo}/contents/{path}/{item['name']}")
            target.write_bytes(base64.b64decode(data["content"]))
            print(f"  {path}/{item['name']}")
        elif item["type"] == "dir":
            download_dir(repo, f"{path}/{item['name']}", target)


def cmd_list(repo: str) -> None:
    for item in api(f"repos/{repo}/contents"):
        if item["type"] == "dir":
            print(item["name"])


def cmd_read(repo: str, slug: str) -> None:
    data = api(f"repos/{repo}/contents/{slug}/SKILL.md")
    print(base64.b64decode(data["content"]).decode())


def cmd_install(repo: str, slug: str) -> None:
    dest = WORKSPACE / "skills" / slug
    if dest.exists():
        import shutil
        shutil.rmtree(dest)
    download_dir(repo, slug, dest)
    print(f"Installed '{slug}' to {dest}")


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__.strip())
        sys.exit(1)

    cmd, repo = sys.argv[1], sys.argv[2]
    slug = sys.argv[3] if len(sys.argv) > 3 else ""

    if cmd == "list":
        cmd_list(repo)
    elif cmd == "read":
        if not slug:
            print("Usage: main.py read <owner/repo> <slug>")
            sys.exit(1)
        cmd_read(repo, slug)
    elif cmd == "install":
        if not slug:
            print("Usage: main.py install <owner/repo> <slug>")
            sys.exit(1)
        cmd_install(repo, slug)
    else:
        print(__doc__.strip())
        sys.exit(1)


if __name__ == "__main__":
    main()
