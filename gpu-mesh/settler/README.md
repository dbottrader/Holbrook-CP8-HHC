# GPU mesh settler

This process runs on the operator's Linux box. It turns a verified GPU-mesh job into an HHCW mint on Base Sepolia.

HHCW is a utility credit for verified contribution. The settler does not sell it and does not promise a return.

The deployer key stays in a file on that box. The hub never receives it. Supabase stores only the settler bearer token `GPU_MESH_SETTLER_TOKEN` (environment or Vault, same name) and the public transaction hash.

## What it submits

`Settlement.sol` (`0xdfFE664d23E30Baff7Ad4d16831aD625Cc90bcCA`) mints HHCW (`0x24a7B22fC54DbFD117023535eBeCf660B76fdb5d`) at 90% to the worker and 5% to each of two verifiers. The three shares must add up to the contribution. One mesh credit is 1000 HHCW units, so the split is exact (900 / 50 / 50 per credit).

The contract has no escrow. A worker or verifier with no payout address is not paid to a stand-in address. The settler posts `skipped_missing_payout`. When that node registers an address, the hub puts the settlement back on the pending list.

A settlement is pending only after two distinct verifiers, neither of them the worker, have agreed with the hub's duplicate check. One node cannot verify its own job. There is no bypass flag.

## Command

From the repository root, with the key file mode `600`:

```bash
PYTHONPATH=. python3 gpu-mesh/settler/settle.py \
  --key-file /workspace/token/.deployer.key \
  --hub https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/gpu-mesh \
  --rpc https://sepolia.base.org \
  --loop
```

`GPU_MESH_SETTLER_TOKEN` must be set in the environment. Do not pass the deployer key as an argument.

`--once` handles the current queue and exits. `--loop` polls every 20 seconds (`--interval` changes that). `--rpc` defaults to `https://sepolia.base.org` because some public RPCs answer 403.

Dependencies: `pip install -r requirements-onchain.txt`.
