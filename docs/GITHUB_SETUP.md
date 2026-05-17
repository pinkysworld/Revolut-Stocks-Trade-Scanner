# GitHub Setup

## Local Repo

This workspace can be initialized locally with git and committed before any remote exists.

## Create a Remote Later

When you are ready to publish it, create a GitHub repository in the web UI or with your preferred CLI, then add the remote:

```bash
git remote add origin git@github.com:<your-user>/<your-repo>.git
```

or

```bash
git remote add origin https://github.com/<your-user>/<your-repo>.git
```

## First Push

```bash
git push -u origin main
```

## Suggested First Commits

1. Commit the code and docs scaffold.
2. Commit any follow-up strategy tuning separately.
3. Keep generated CSV outputs untracked unless you intentionally want snapshots.

## Recommended Repo Contents

- scanner source files
- instrument universe CSV
- Markdown docs under `docs/`
- `.gitignore`
- changelog

## What Is Not Automatically Created Here

A live GitHub remote repository is not created automatically by this workspace setup because that requires your GitHub destination, account, and remote-auth preference.
