-- Named Vault lookup for edge functions, and retirement of the unused signer.
--
-- cp8_private is not a Data API schema until PostgREST is told about it below.
-- The helper is SECURITY DEFINER so it can read vault.decrypted_secrets, and
-- EXECUTE is granted only to service_role. The body also rejects every JWT
-- role other than service_role. It returns the secret text to that role and
-- must not be called from a browser.
--
-- The public key c30d2e6d...e905 was published without a stored seed. It cannot
-- sign. Remove that row. The groq-test function publishes the public key it
-- derives from INFERENCE_RECEIPT_SIGNING_KEY or the Vault entry
-- inference_receipt_signing_key. Only the public key is written.

create schema if not exists cp8_private;

revoke all on schema cp8_private from public, anon, authenticated;
grant usage on schema cp8_private to service_role;

create or replace function cp8_private.read_named_secret(secret_name text)
returns text
language plpgsql
security definer
set search_path = ''
as $$
declare
  jwt_role text := '';
  result text;
begin
  begin
    jwt_role := coalesce(current_setting('request.jwt.claim.role', true), '');
  exception
    when others then
      jwt_role := '';
  end;
  if jwt_role = '' then
    begin
      jwt_role := coalesce((current_setting('request.jwt.claims', true))::json ->> 'role', '');
    exception
      when others then
        jwt_role := '';
    end;
  end if;
  if jwt_role is distinct from 'service_role' then
    raise exception 'forbidden' using errcode = '42501';
  end if;
  if secret_name is null or secret_name !~ '^[a-z][a-z0-9_]{0,63}$' then
    return null;
  end if;
  select ds.decrypted_secret
    into result
  from vault.decrypted_secrets as ds
  where ds.name = secret_name
  order by ds.created_at desc
  limit 1;
  return result;
end;
$$;

revoke all on function cp8_private.read_named_secret(text) from public, anon, authenticated;
grant execute on function cp8_private.read_named_secret(text) to service_role;

comment on function cp8_private.read_named_secret(text) is
  'Returns one Vault secret by name. Executable only by service_role.';

-- Let the service-role Data API see this one function. anon and authenticated
-- still have no privilege on the schema. Hosted projects can also add
-- cp8_private under Settings > API > Exposed schemas if this role setting is
-- reset by the platform.
do $$
declare
  schemas text := 'public, graphql_public, cp8_private';
  existing text;
begin
  select split_part(cfg, '=', 2)
    into existing
  from pg_roles as r
  cross join lateral unnest(coalesce(r.rolconfig, array[]::text[])) as cfg
  where r.rolname = 'authenticator'
    and cfg like 'pgrst.db_schemas=%'
  limit 1;
  if existing is not null and position('cp8_private' in existing) = 0 then
    schemas := existing || ', cp8_private';
  elsif existing is not null then
    schemas := existing;
  end if;
  execute format('alter role authenticator set pgrst.db_schemas = %L', schemas);
end $$;

notify pgrst, 'reload config';

delete from public.cp8_inference_signer
where id = 1
  and public_key_hex = 'c30d2e6d53443bede57190391a61738dba6fc491c098cc1ac38e07d17eade905';

grant select, insert, update on public.cp8_inference_signer to service_role;
