-- Named Vault lookup for edge functions, and retirement of the unused signer.
--
-- cp8_private is not added to the Data API schemas by this migration.
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

-- cp8_private stays out of the Data API. The edge function calls this helper
-- with the service-role JWT when the schema is exposed, and otherwise through
-- the function's database connection after setting request.jwt.claim.role.
-- Dennis can add cp8_private under Settings > API > Exposed schemas. anon and
-- authenticated have no privilege on the schema either way.

delete from public.cp8_inference_signer
where id = 1
  and public_key_hex = 'c30d2e6d53443bede57190391a61738dba6fc491c098cc1ac38e07d17eade905';

grant select, insert, update on public.cp8_inference_signer to service_role;
