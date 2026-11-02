-- Replace the published inference receipt signer.
-- The previous public key stays in git history. Its seed was disclosed, so
-- this row must not keep trusting it. Only the public key is stored here.

update public.cp8_inference_signer
set public_key_hex = 'c30d2e6d53443bede57190391a61738dba6fc491c098cc1ac38e07d17eade905'
where id = 1;
