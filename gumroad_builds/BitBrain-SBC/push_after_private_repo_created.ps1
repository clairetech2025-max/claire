$ErrorActionPreference = "Stop"

$Repo = "git@github.com:Claire-Systems/bitbrain-sbc-private.git"
$PayloadDir = "/home/LuciusPrime/claire/private_repo_payloads/bitbrain-sbc-private"

Set-Location $PayloadDir

if (!(Test-Path ".git")) {
    git init
}

git branch -M main
git add .

git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m "initial private BitBrain SBC Gumroad release"
} else {
    Write-Host "No staged changes to commit."
}

git remote get-url origin *> $null
if ($LASTEXITCODE -eq 0) {
    git remote set-url origin $Repo
} else {
    git remote add origin $Repo
}

git push -u origin main
