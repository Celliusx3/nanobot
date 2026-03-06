# Contributing

## Syncing your fork with upstream

This project is forked from [HKUDS/nanobot](https://github.com/HKUDS/nanobot). To keep your fork up to date:

### First-time setup

```bash
git remote add upstream https://github.com/HKUDS/nanobot.git
```

### Sync with upstream

```bash
git fetch upstream
git rebase upstream/main
git push --force-with-lease
```

### If you hit conflicts

```bash
# Fix the conflicting files, then:
git add <fixed-files>
git rebase --continue

# Or abort and go back to before the rebase:
git rebase --abort
```
