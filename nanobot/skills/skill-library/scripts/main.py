#!/usr/bin/env python3
"""Skill library — browse, install, and publish skills from a GitHub repo.

Usage:
    main.py list    <owner/repo>
    main.py read    <owner/repo> <slug>
    main.py install <owner/repo> <slug>
    main.py push    <owner/repo> <slug>
    main.py delete  <owner/repo> <slug>
"""

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

WORKSPACE = Path(os.environ.get("NANOBOT_WORKSPACE", Path.home() / ".nanobot" / "workspace"))


def api(endpoint: str) -> any:
    """Call GitHub API (GET) and return parsed JSON."""
    url = f"https://api.github.com/{endpoint}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.environ.get("GH_TOKEN", "")
    if token:
        headers["Authorization"] = f"token {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def api_write(endpoint: str, data: dict, method: str = "POST") -> any:
    """Call GitHub API with a JSON body (POST/PUT/PATCH)."""
    url = f"https://api.github.com/{endpoint}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }
    token = os.environ.get("GH_TOKEN", "")
    if token:
        headers["Authorization"] = f"token {token}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
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


def collect_files(directory: Path, prefix: str = "") -> list[tuple[str, bytes]]:
    """Recursively collect all files as (relative_path, content) tuples."""
    files = []
    for item in sorted(directory.iterdir()):
        rel = f"{prefix}/{item.name}" if prefix else item.name
        if item.is_file():
            files.append((rel, item.read_bytes()))
        elif item.is_dir():
            files.extend(collect_files(item, rel))
    return files


# ── Read-only commands ──────────────────────────────────────────────


def cmd_list(repo: str) -> None:
    for item in api(f"repos/{repo}/contents"):
        if item["type"] == "dir":
            print(item["name"])


def cmd_read(repo: str, slug: str) -> None:
    data = api(f"repos/{repo}/contents/{slug}/SKILL.md")
    print(base64.b64decode(data["content"]).decode())


def cmd_install(repo: str, slug: str) -> None:
    import shutil
    dest = WORKSPACE / "skills" / slug
    if dest.exists():
        shutil.rmtree(dest)
    download_dir(repo, slug, dest)
    # Install pip dependencies locally into vendor/ if requirements.txt exists
    req_file = dest / "requirements.txt"
    if req_file.exists():
        import subprocess
        vendor_dir = dest / "vendor"
        vendor_dir.mkdir(exist_ok=True)
        print(f"Installing dependencies into {vendor_dir}...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "--target", str(vendor_dir),
            "-r", str(req_file),
        ])
        # Clean up metadata and caches to save space
        for p in vendor_dir.glob("*.dist-info"):
            shutil.rmtree(p)
        for p in vendor_dir.rglob("__pycache__"):
            shutil.rmtree(p)
    print(f"Installed '{slug}' to {dest}")


# ── Write commands ──────────────────────────────────────────────────


def cmd_push(repo: str, slug: str) -> None:
    """Push a local skill to the GitHub repo as a single commit."""
    src = WORKSPACE / "skills" / slug
    if not src.exists():
        print(f"Error: skill '{slug}' not found at {src}")
        sys.exit(1)
    if not (src / "SKILL.md").exists():
        print(f"Error: {src}/SKILL.md not found — not a valid skill")
        sys.exit(1)

    files = collect_files(src)
    if not files:
        print("Error: no files to push")
        sys.exit(1)

    # 1. Get current main branch HEAD
    ref = api(f"repos/{repo}/git/ref/heads/main")
    head_sha = ref["object"]["sha"]
    commit = api(f"repos/{repo}/git/commits/{head_sha}")
    base_tree_sha = commit["tree"]["sha"]

    # 2. Create blobs for each file
    tree_items = []
    for rel_path, content in files:
        blob = api_write(f"repos/{repo}/git/blobs", {
            "content": base64.b64encode(content).decode(),
            "encoding": "base64",
        })
        tree_items.append({
            "path": f"{slug}/{rel_path}",
            "mode": "100644",
            "type": "blob",
            "sha": blob["sha"],
        })
        print(f"  {slug}/{rel_path}")

    # 3. Create tree
    tree = api_write(f"repos/{repo}/git/trees", {
        "base_tree": base_tree_sha,
        "tree": tree_items,
    })

    # 4. Create commit
    new_commit = api_write(f"repos/{repo}/git/commits", {
        "message": f"Add skill: {slug}",
        "tree": tree["sha"],
        "parents": [head_sha],
    })

    # 5. Update main ref
    api_write(f"repos/{repo}/git/refs/heads/main", {
        "sha": new_commit["sha"],
    }, method="PATCH")

    print(f"\nPushed '{slug}' to {repo} ({new_commit['sha'][:7]})")


def cmd_delete(repo: str, slug: str) -> None:
    """Remove a skill from the GitHub repo as a single commit."""
    # 1. Get current tree and find all files under slug/
    ref = api(f"repos/{repo}/git/ref/heads/main")
    head_sha = ref["object"]["sha"]
    commit = api(f"repos/{repo}/git/commits/{head_sha}")
    base_tree_sha = commit["tree"]["sha"]

    # Get full tree recursively to find files under slug/
    full_tree = api(f"repos/{repo}/git/trees/{base_tree_sha}?recursive=1")
    to_keep = [
        item for item in full_tree["tree"]
        if not item["path"].startswith(f"{slug}/")
    ]
    removed = [
        item for item in full_tree["tree"]
        if item["path"].startswith(f"{slug}/") and item["type"] == "blob"
    ]

    if not removed:
        print(f"Error: skill '{slug}' not found in {repo}")
        sys.exit(1)

    for item in removed:
        print(f"  Removing {item['path']}")

    # 2. Create new tree without the skill's files
    new_tree = api_write(f"repos/{repo}/git/trees", {
        "tree": [
            {"path": item["path"], "mode": item["mode"], "type": item["type"], "sha": item["sha"]}
            for item in to_keep
            if item["type"] == "blob"
        ],
    })

    # 3. Create commit
    new_commit = api_write(f"repos/{repo}/git/commits", {
        "message": f"Remove skill: {slug}",
        "tree": new_tree["sha"],
        "parents": [head_sha],
    })

    # 4. Update main ref
    api_write(f"repos/{repo}/git/refs/heads/main", {
        "sha": new_commit["sha"],
    }, method="PATCH")

    print(f"\nRemoved '{slug}' from {repo} ({new_commit['sha'][:7]})")


# ── CLI entry point ─────────────────────────────────────────────────


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
    elif cmd == "push":
        if not slug:
            print("Usage: main.py push <owner/repo> <slug>")
            sys.exit(1)
        cmd_push(repo, slug)
    elif cmd == "delete":
        if not slug:
            print("Usage: main.py delete <owner/repo> <slug>")
            sys.exit(1)
        cmd_delete(repo, slug)
    else:
        print(__doc__.strip())
        sys.exit(1)


if __name__ == "__main__":
    main()
