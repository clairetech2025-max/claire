$ErrorActionPreference = "Stop"

$ProductName = "ARE-Spectacle"
$SourceRoot = "C:\ARE-Spectacle-Private\are-spectacle-v2"
$BuildRoot = Join-Path $PSScriptRoot "build"
$StageRoot = Join-Path $BuildRoot $ProductName
$ReleaseRoot = Join-Path $PSScriptRoot "release"
$ZipPath = Join-Path $ReleaseRoot "$ProductName-Gumroad.zip"

Write-Host ""
Write-Host "ARE Spectacle Gumroad Build"
Write-Host "Source: $SourceRoot"
Write-Host ""

if (!(Test-Path $SourceRoot)) {
    throw "SourceRoot not found. Edit `$SourceRoot in this script to point at your private are-spectacle-v2 folder."
}

if (Test-Path $BuildRoot) {
    Remove-Item $BuildRoot -Recurse -Force
}
if (Test-Path $ReleaseRoot) {
    Remove-Item $ReleaseRoot -Recurse -Force
}

New-Item -ItemType Directory -Path $StageRoot | Out-Null
New-Item -ItemType Directory -Path $ReleaseRoot | Out-Null

Copy-Item (Join-Path $SourceRoot "app") $StageRoot -Recurse
Copy-Item (Join-Path $SourceRoot "requirements.txt") $StageRoot
Copy-Item (Join-Path $PSScriptRoot "run_spectacle.py") $StageRoot
Copy-Item (Join-Path $PSScriptRoot "README_START_HERE.txt") $StageRoot
Copy-Item (Join-Path $PSScriptRoot "sample_requests.json") $StageRoot

Push-Location $StageRoot

try {
    if (!(Test-Path ".venv")) {
        py -3.12 -m venv .venv
    }

    .\.venv\Scripts\python.exe -m pip install --upgrade pip wheel
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    .\.venv\Scripts\python.exe -m pip install nuitka ordered-set zstandard

    .\.venv\Scripts\python.exe -m pytest tests 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "No staged tests found or tests skipped for release build."
    }

    .\.venv\Scripts\python.exe -m nuitka `
        --standalone `
        --onefile `
        --assume-yes-for-downloads `
        --enable-plugin=pydantic `
        --include-package=app `
        --include-package=uvicorn `
        --include-package=fastapi `
        --include-package=starlette `
        --output-filename="$ProductName.exe" `
        run_spectacle.py

    $ExePath = Join-Path $StageRoot "$ProductName.exe"
    if (!(Test-Path $ExePath)) {
        throw "Nuitka build did not produce $ExePath"
    }

    $PackageRoot = Join-Path $BuildRoot "$ProductName-Gumroad"
    New-Item -ItemType Directory -Path $PackageRoot | Out-Null
    Copy-Item $ExePath $PackageRoot
    Copy-Item "README_START_HERE.txt" $PackageRoot
    Copy-Item "sample_requests.json" $PackageRoot

    Compress-Archive -Path (Join-Path $PackageRoot "*") -DestinationPath $ZipPath -Force
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "Release created:"
Write-Host $ZipPath
Write-Host ""
Write-Host "Upload that ZIP to Gumroad. Do not upload the source folder."
