# Gumroad Build Pattern

Use the same release pattern for each standalone product:

1. Keep source private.
2. Store that source in a private GitHub repo.
3. Add a tiny launcher beside the private source.
4. Compile with Nuitka on GitHub Actions Windows runners.
5. Ship only the executable, buyer README, examples, and license text.
5. Exclude `.py`, `.venv`, `venv`, `__pycache__`, `.pytest_cache`, databases, logs, and private docs from the final ZIP.

Default release shape:

```text
Product-Gumroad.zip
  Product.exe
  README_START_HERE.txt
  sample_requests.json
```

Use PyInstaller only for fast internal testing. Use Nuitka for paid downloadable products.

For hosted products, ship a thin client executable and keep the core service server-side.

Do not depend on Azure for release storage or build output. Azure can host demos, but GitHub private repos and GitHub Releases should hold the durable product chain.
