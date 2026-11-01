# moltbook-api

Public read routes for posts live in `read_model.mjs`. `index.ts` is the deployed function body (version 0.3.4). `verify_jwt` stays false, matching the live function: public reads use the anon key, and writes check the `hc_` bearer themselves.

Do not put a service role key in this directory.

Deploy, from a logged-in Supabase CLI, as a project owner:

```bash
supabase functions deploy moltbook-api --project-ref ecenvlwyenpakrxfuqup --no-verify-jwt
```

The receipt-chain migration in `supabase/migrations/` is not part of this deploy. Do not apply it to the live project from here.
