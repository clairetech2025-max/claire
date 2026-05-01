# Create The Private Gumroad Repos

The GitHub connector in this session can write to existing repositories, but it cannot create new repositories.

Create these as **private** repos in the `Claire-Systems` organization:

```text
Claire-Systems/are-spectacle-private
Claire-Systems/sovereign-execution-gateway-private
Claire-Systems/veritas-parser-private
Claire-Systems/apex-scout-private
Claire-Systems/crown-jewel-parser-private
Claire-Systems/clairepay-demo-private
```

Start with:

```text
Claire-Systems/are-spectacle-private
```

Then create:

```text
Claire-Systems/sovereign-execution-gateway-private
```

Settings:

```text
Visibility: Private
Initialize with README: No
Add .gitignore: No
Add license: No
```

After creating the repo, push:

```bash
cd /home/LuciusPrime/claire/private_repo_payloads/are-spectacle-private
git init
git branch -M main
git add .
git commit -m "initial private ARE Spectacle Gumroad release"
git remote add origin git@github.com:Claire-Systems/are-spectacle-private.git
git push -u origin main
```

Then run the GitHub Actions workflow:

```text
Build Gumroad Windows Release
```

The output artifact is:

```text
ARE-Spectacle-Gumroad.zip
```

Upload that ZIP to Gumroad.

## Sovereign Execution Gateway Push

After creating `Claire-Systems/sovereign-execution-gateway-private`, run:

```bash
/home/LuciusPrime/claire/gumroad_builds/Sovereign-Execution-Gateway/push_after_private_repo_created.sh
```
