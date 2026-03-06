---
name: skill-library
description: Browse, install, and publish skills from a personal GitHub skill library.
metadata: {"nanobot":{"emoji":"📚"}}
---

# Skill Library

Personal skill library hosted on GitHub. Search by browsing, install individually, publish new skills.

## When to use

Use this skill when the user asks any of:
- "find a skill for …"
- "what skills are in my library?"
- "install a skill"
- "update my skills"
- "remove a skill"
- "publish a skill"
- "push my skill to the repo"

## Search

```bash
python3 scripts/main.py list <owner/repo>
```

To read a skill's description before installing:

```bash
python3 scripts/main.py read <owner/repo> <slug>
```

## Install

```bash
python3 scripts/main.py install <owner/repo> <slug>
```

## Publish

Push a locally-created skill to the remote library (single commit):

```bash
python3 scripts/main.py push <owner/repo> <slug>
```

This uploads all files from `~/.nanobot/workspace/skills/<slug>/` to the repo.

## Update

Re-install to get the latest version (same as install — overwrites existing files).
Re-push to update a published skill (same as push — overwrites existing files).

## List installed

```bash
ls ~/.nanobot/workspace/skills/
```

## Remove

Remove locally:

```bash
rm -rf ~/.nanobot/workspace/skills/<slug>
```

Remove from remote library:

```bash
python3 scripts/main.py delete <owner/repo> <slug>
```

## Notes

- No extra tools needed — uses Python stdlib only (urllib).
- Downloads and uploads only the specific skill, not the entire repo.
- For private repos, set `GH_TOKEN` environment variable.
- No restart needed — installed skills are picked up on the next message.
- If a skill is not found here, fall back to ClawHub: `npx --yes clawhub@latest search "<query>"`.
