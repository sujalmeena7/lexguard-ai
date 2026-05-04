#!/usr/bin/env bash
# Sync GitLab main → GitHub main (triggers Vercel/Render deploy)
set -e
echo "Fetching from GitLab..."
git fetch gitlab
echo "Merging gitlab/main into local main..."
git merge gitlab/main --no-edit
echo "Pushing to GitHub (origin/main)..."
git push origin main
echo "Done — GitHub updated, deployments should trigger."
