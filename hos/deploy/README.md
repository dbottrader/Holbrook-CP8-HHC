# Deployment

Build from the repository root so the Dockerfile can copy `hos/`.

```bash
docker build -f hos/deploy/Dockerfile -t asinhhccp8-hos .
docker run --rm -p 8000:8000 asinhhccp8-hos
```

Set `SUPABASE_URL` and `SUPABASE_ANON_KEY` only when persistence is required. Do not expose a service-role key to a public runtime.
