-- The public coordinator must not keep a signing seed in a table.
-- Fresh installs never create private_hex. This drops it where an earlier
-- draft stored one. The live public key is derived from
-- INFERENCE_RECEIPT_SIGNING_KEY or Vault name inference_receipt_signing_key.

alter table public.gpumesh_signer drop column if exists private_hex;
