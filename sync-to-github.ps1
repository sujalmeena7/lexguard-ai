# Sync GitLab main -> GitHub main (triggers Vercel/Render deploy)
Write-Host "Fetching from GitLab..."
git fetch gitlab
Write-Host "Merging gitlab/main into local main..."
git merge gitlab/main --no-edit
Write-Host "Pushing to GitHub (origin/main)..."
git push origin main
Write-Host "Done - GitHub updated, deployments should trigger."
