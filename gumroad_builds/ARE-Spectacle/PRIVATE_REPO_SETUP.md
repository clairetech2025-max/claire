# Private GitHub Repo Setup

Use a private repo for the product source and GitHub Actions release build.

Recommended repo:

```text
Claire-Systems/are-spectacle-private
```

Keep it private. Do not use the existing public repos for private source.

## Files The Private Repo Should Contain

```text
app/
tests/
requirements.txt
run_spectacle.py
README_START_HERE.txt
sample_requests.json
.github/workflows/build-gumroad-windows.yml
```

The Gumroad ZIP produced by the workflow contains only:

```text
ARE-Spectacle.exe
README_START_HERE.txt
sample_requests.json
```

## Build Flow

1. Push source to the private repo.
2. Run the `Build Gumroad Windows Release` workflow manually, or push a tag like `v1.0.0`.
3. Download the `ARE-Spectacle-Gumroad` artifact or use the GitHub Release asset.
4. Upload that ZIP to Gumroad.

## Why This Survives Azure Failure

GitHub stores the private source and release artifacts.
GitHub Actions builds the Windows executable.
Gumroad receives only the compiled buyer package.

Azure is not part of the release chain.
