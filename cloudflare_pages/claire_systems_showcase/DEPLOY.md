# CLAIRE Systems Showcase Deployment

This folder is a static Cloudflare Pages site for `clairesystems.ai`.

It does not replace the Hugging Face Spaces:

- ARE Memory Module: https://blackstormhorse-are-memory-module.hf.space/
- CLAIRE Control Interface: https://blackstormhorse-claire-control-interface.hf.space/

## Local Test

```bash
cd /home/LuciusPrime/claire/cloudflare_pages/claire_systems_showcase
python3 -m http.server 8787 --bind 127.0.0.1
```

Open:

```text
http://127.0.0.1:8787
```

## Cloudflare Pages Deploy

The VM needs a Cloudflare API token in the environment. Do not paste or commit the token into a file.

```bash
export CLOUDFLARE_API_TOKEN='paste-token-here'
cd /home/LuciusPrime/claire/cloudflare_pages/claire_systems_showcase
CI=1 npx wrangler@3.114.14 pages deploy . --project-name claire-systems-showcase --commit-dirty=true
```

After deployment, attach the custom domain in Cloudflare Pages:

```text
clairesystems.ai
```

Use Cloudflare dashboard if preferred:

1. Cloudflare Dashboard
2. Workers & Pages
3. Create or open `claire-systems-showcase`
4. Upload this static folder
5. Add custom domain `clairesystems.ai`

## Safety

This site contains only public-safe sales/showcase copy and outbound links to the public Hugging Face demos. It contains no secrets, private memory, account files, legal files, trader files, production backend, or Azure dependency.
