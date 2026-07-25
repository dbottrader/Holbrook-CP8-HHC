# Supabase Adapter

The historical project record references a Supabase HOS lattice, but those references are not treated as proof of a currently active database. This package therefore uses environment variables and a reproducible SQL schema.

1. Create or select a Supabase project.
2. Run `schema.sql` in the SQL editor.
3. Copy `.env.example` to `.env` and supply the project URL and public anon key.
4. Keep the service-role key out of the browser and out of GitHub.
5. Add an authenticated row-level-security policy before allowing writes.
