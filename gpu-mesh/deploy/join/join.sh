#!/usr/bin/env bash
# ASIN-HHC GPU Mesh - one-command join (Linux and macOS, no Docker, no sudo).
#
#   curl -fsSL https://raw.githubusercontent.com/dbottrader/Holbrook-CP8-HHC/main/gpu-mesh/deploy/join/join.sh | bash
#   curl -fsSL .../join.sh | bash -s -- --payout-address 0xYourEvmAddress
#
# What it does, in order. Every step prints PASS or FAIL and stops on FAIL.
#   1. Checks curl and python3 3.11+ (or installs uv in your home dir to get one).
#   2. Installs the node agent into a venv in ~/.asin-hhc.
#   3. Downloads the pinned Ollama release (sha256 checked) into ~/.asin-hhc and
#      keeps only its AVX2 ("haswell") CPU backend. That is the canonical
#      verifier runtime: greedy output differs between CPU kernels (AVX-512/AMX
#      vs AVX2) and between CPU and GPU, so every verifier runs the same one.
#      It runs privately on 127.0.0.1:11435 with its own model folder, so your
#      own Ollama and models are never touched or advertised.
#   4. Downloads the pinned GGUF and checks its sha256.
#   5. Builds asin-qwen0.5b from the committed Modelfile and checks the Ollama
#      manifest digest. Only this exact digest can claim verification jobs.
#   6. Compatibility check: replays public mesh job job_17da8f18d97f and requires
#      the output hash its worker and its first verifier both produced. A machine that cannot
#      reproduce it would disagree with honest work, so it is not started.
#   7. Registers a node identity (token stays in ~/.asin-hhc/node.json, mode 600)
#      and runs the worker in the background. It claims work and verifies other
#      nodes' jobs. A node never verifies its own job.
#
# HHC is a utility credit for verified contribution. It is not sold and pays no return.
# Stop: bash ~/.asin-hhc/stop.sh    Logs: tail -f ~/.asin-hhc/node.log
set -euo pipefail

COORD="${GPU_MESH_COORDINATOR:-https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/gpu-mesh}"
REPO_RAW="https://raw.githubusercontent.com/dbottrader/Holbrook-CP8-HHC"
REF="${ASIN_HHC_REF:-main}"
HOME_DIR="${ASIN_HHC_HOME:-$HOME/.asin-hhc}"
PORT="${ASIN_HHC_OLLAMA_PORT:-11435}"
NAME=""
PAYOUT="${GPU_MESH_PAYOUT_ADDRESS:-}"
SOURCE=""          # local checkout of the repo (for tests); default installs from GitHub
OLLAMA_BIN="${OLLAMA_BIN:-}"   # experimental override, skips the canonical runtime
FOREGROUND=0
DRY=0
SMOKE=0

# Pins. Keep in sync with .github/workflows/checker-node.yml and tests/test_join_oneline.py.
MODEL_TAG="asin-qwen0.5b:latest"
MODEL_NAME="asin-qwen0.5b"
MODEL_DIGEST="29ef26c5cf7d3d68a20fdeb8664ef48f1f32386d2ba09ddb4b19f4c7dc89d5de"
GGUF_FILE="qwen2.5-0.5b-instruct-q4_k_m.gguf"
GGUF_URL="https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/${GGUF_FILE}"
GGUF_SHA256="74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db"
OLLAMA_VERSION="0.40.15"
OLLAMA_LINUX_AMD64_SHA="628c018404a4206493efd38e46251c154ede5141b8b8dc85c659b3b027c47379"
OLLAMA_LINUX_ARM64_SHA="7f699ead5cdb4ae1ed89b888b148a238af188708800871e1889ab9dcee95f247"
CPU_BACKEND="libggml-cpu-haswell.so"
# Reference job for the compatibility check (public: $COORD/v1/jobs/job_17da8f18d97f).
REF_JOB="job_17da8f18d97f"
REF_PROMPT="Reply with the single word mesh"
REF_SEED=1674994887
REF_OUTPUT_SHA="d30ca7a7a32bf5772dc5eb2a2e7bd35737eff795ad74f2479b359716b59abdfa"

usage() {
  cat >&2 <<USAGE
Usage: join.sh [--payout-address 0x...] [--name NAME] [--coordinator URL]
               [--home DIR] [--port N] [--source CHECKOUT] [--ollama-bin PATH]
               [--foreground] [--smoke] [--dry-run]
  --payout-address  EVM address that receives this node's HHCW on Base Sepolia (optional).
  --smoke           After joining, send one public test request so the mesh has work.
  --foreground      Run the worker in this terminal instead of the background.
  --dry-run         Print the plan and pins, change nothing.
  --ollama-bin      Experimental: use this Ollama instead of the canonical runtime.
                    Your node may then disagree with honest work and earn nothing.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --payout-address) PAYOUT="${2:-}"; shift 2 ;;
    --name) NAME="${2:-}"; shift 2 ;;
    --coordinator) COORD="${2:-}"; shift 2 ;;
    --home) HOME_DIR="${2:-}"; shift 2 ;;
    --port) PORT="${2:-}"; shift 2 ;;
    --ollama-bin) OLLAMA_BIN="${2:-}"; shift 2 ;;
    --source) SOURCE="${2:-}"; shift 2 ;;
    --foreground) FOREGROUND=1; shift ;;
    --smoke) SMOKE=1; shift ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

pass() { printf '  PASS  %s\n' "$*"; }
fail() {
  printf '  FAIL  %s\n' "$*" >&2
  # Stop the private Ollama this run started, unless a worker is already using it.
  if [[ -f "$HOME_DIR/ollama.pid" && ! -f "$HOME_DIR/node.pid" ]]; then
    kill "$(cat "$HOME_DIR/ollama.pid")" 2>/dev/null || true; rm -f "$HOME_DIR/ollama.pid"
  fi
  exit 1
}
step() { printf '\n[%s] %s\n' "$1" "$2"; }

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
  else shasum -a 256 "$1" | awk '{print $1}'; fi
}

COORD="${COORD%/}"
if [[ -n "$PAYOUT" ]]; then
  [[ "$PAYOUT" =~ ^0x[0-9a-fA-F]{40}$ ]] || fail "payout address must be 0x plus 40 hex characters"
  [[ ! "$PAYOUT" =~ ^0x0{40}$ ]] || fail "payout address must not be the zero address"
fi
if [[ -z "$NAME" ]]; then
  NAME="vol-$( (hostname -s 2>/dev/null || hostname) | tr -cd 'A-Za-z0-9-' | cut -c1-20)"
fi
OS="$(uname -s)"; ARCH="$(uname -m)"
OLLAMA_URL="http://127.0.0.1:${PORT}"

echo "ASIN-HHC GPU Mesh join"
echo "  coordinator  $COORD"
echo "  node name    $NAME"
echo "  home         $HOME_DIR"
echo "  model        $MODEL_TAG  digest ${MODEL_DIGEST:0:12}"
echo "  runtime      Ollama $OLLAMA_VERSION, $CPU_BACKEND only, 127.0.0.1:$PORT"
echo "  gguf sha256  ${GGUF_SHA256:0:12}"
echo "  payout       ${PAYOUT:-none (credits stay on the node identity)}"
if [[ "$DRY" == "1" ]]; then echo "dry run: nothing changed"; exit 0; fi

mkdir -p "$HOME_DIR"; chmod 700 "$HOME_DIR"

# 1. Prerequisites -----------------------------------------------------------
step 1/7 "Prerequisites"
if [[ -z "$OLLAMA_BIN" ]]; then
  if [[ "$OS" != "Linux" || "$ARCH" != "x86_64" ]]; then
    fail "the canonical verifier runtime is Linux x86_64 for now (WSL2 on Windows works). $OS $ARCH replays are not yet proven to match. See https://github.com/dbottrader/Holbrook-CP8-HHC/blob/main/CONTRIBUTING-GPU.md"
  fi
  grep -qw avx2 /proc/cpuinfo || fail "this CPU has no AVX2, the canonical verifier backend needs it"
fi
pass "platform $OS $ARCH"
command -v curl >/dev/null 2>&1 || fail "curl is required"
curl -fsS -m 20 "$COORD/health" -o "$HOME_DIR/health.json" || fail "coordinator $COORD/health is not reachable"
pass "coordinator reachable"
PY=""
for cand in python3.13 python3.12 python3.11 python3; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import sys,venv,ensurepip; sys.exit(0 if sys.version_info>=(3,11) else 1)' 2>/dev/null; then
    PY="$(command -v "$cand")"; break
  fi
done
USE_UV=0
if [[ -z "$PY" ]]; then
  if ! command -v uv >/dev/null 2>&1 && [[ ! -x "$HOME_DIR/bin/uv" ]]; then
    echo "  no usable python 3.11+, installing uv into $HOME_DIR/bin (user space, no sudo)"
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$HOME_DIR/bin" UV_NO_MODIFY_PATH=1 sh >/dev/null
  fi
  UV="$(command -v uv 2>/dev/null || echo "$HOME_DIR/bin/uv")"
  [[ -x "$UV" ]] || fail "could not get python 3.11+ or uv"
  USE_UV=1
  pass "uv will provide python 3.12"
else
  pass "python $("$PY" -c 'import platform;print(platform.python_version())')"
fi

# 2. Node agent --------------------------------------------------------------
step 2/7 "Node agent"
VPY="$HOME_DIR/venv/bin/python"
if [[ ! -x "$VPY" ]]; then
  if [[ "$USE_UV" == "1" ]]; then "$UV" venv -q --python 3.12 "$HOME_DIR/venv"
  else "$PY" -m venv "$HOME_DIR/venv"; fi
fi
if [[ -n "$SOURCE" ]]; then spec="$SOURCE/gpu-mesh"
else spec="gpumesh @ https://github.com/dbottrader/Holbrook-CP8-HHC/archive/${REF}.tar.gz#subdirectory=gpu-mesh"; fi
if [[ "$USE_UV" == "1" ]]; then "$UV" pip install -q --python "$VPY" "$spec" zstandard >"$HOME_DIR/pip.log" 2>&1 || { tail -20 "$HOME_DIR/pip.log" >&2; fail "pip install failed"; }
else { "$VPY" -m pip install -q --upgrade pip && "$VPY" -m pip install -q "$spec" zstandard; } >"$HOME_DIR/pip.log" 2>&1 || { tail -20 "$HOME_DIR/pip.log" >&2; fail "pip install failed"; }; fi
"$VPY" -c 'import gpumesh_node.agent, zstandard' || fail "node agent import failed"
pass "gpumesh_node installed in $HOME_DIR/venv"

# 3. Canonical Ollama runtime -------------------------------------------------
step 3/7 "Canonical verifier runtime (Ollama $OLLAMA_VERSION, AVX2 CPU backend)"
if [[ -n "$OLLAMA_BIN" ]]; then
  echo "  WARNING: --ollama-bin $OLLAMA_BIN is not the canonical runtime. Step 6 decides if it can verify."
else
  OLLAMA_BIN="$HOME_DIR/ollama/bin/ollama"
  if [[ ! -x "$OLLAMA_BIN" || ! -f "$HOME_DIR/ollama/.pinned-$OLLAMA_VERSION" ]]; then
    rm -rf "$HOME_DIR/ollama"; mkdir -p "$HOME_DIR/ollama"
    asset="ollama-linux-amd64.tar.zst"
    echo "  downloading $asset v$OLLAMA_VERSION (about 1.5 GB, once)"
    curl -fsSL --retry 3 -o "$HOME_DIR/ollama/$asset" "https://github.com/ollama/ollama/releases/download/v${OLLAMA_VERSION}/${asset}"
    [[ "$(sha256_of "$HOME_DIR/ollama/$asset")" == "$OLLAMA_LINUX_AMD64_SHA" ]] || fail "Ollama archive sha256 mismatch"
    pass "Ollama archive sha256 ${OLLAMA_LINUX_AMD64_SHA:0:12}"
    "$VPY" - "$HOME_DIR/ollama/$asset" "$HOME_DIR/ollama" "$CPU_BACKEND" <<'PYX'
import os, sys, tarfile, zstandard
archive, dest, keep = sys.argv[1:4]
def wanted(name):
    parts = name.lstrip("./").split("/")
    if len(parts) >= 3 and parts[0] == "lib" and parts[1] == "ollama":
        leaf = parts[2]
        if leaf.startswith(("cuda_", "rocm", "mlx", "vulkan")):
            return False
        if leaf.startswith("libggml-cpu-") and leaf != keep:
            return False
    return True
with open(archive, "rb") as fh:
    reader = zstandard.ZstdDecompressor().stream_reader(fh)
    with tarfile.open(fileobj=reader, mode="r|") as tar:
        for member in tar:
            if wanted(member.name):
                tar.extract(member, dest, filter="tar") if hasattr(tarfile, "tar_filter") else tar.extract(member, dest)
PYX
    rm -f "$HOME_DIR/ollama/$asset"
    touch "$HOME_DIR/ollama/.pinned-$OLLAMA_VERSION"
  fi
  [[ -x "$OLLAMA_BIN" ]] || fail "Ollama binary missing after unpacking"
  cpu_libs="$(cd "$HOME_DIR/ollama/lib/ollama" && ls libggml-cpu-*.so 2>/dev/null | tr '\n' ' ')"
  [[ "$cpu_libs" == "$CPU_BACKEND " ]] || fail "expected only $CPU_BACKEND, found: $cpu_libs"
  pass "CPU backend pinned to $CPU_BACKEND, GPU backends removed"
fi
mkdir -p "$HOME_DIR/models"
if curl -fs -m 3 "$OLLAMA_URL/api/version" >/dev/null 2>&1; then
  if ! { [[ -f "$HOME_DIR/ollama.pid" ]] && kill -0 "$(cat "$HOME_DIR/ollama.pid")" 2>/dev/null; }; then
    fail "something else is already serving on $OLLAMA_URL. Stop it or pass --port N"
  fi
else
  OLLAMA_HOST="127.0.0.1:${PORT}" OLLAMA_MODELS="$HOME_DIR/models" nohup "$OLLAMA_BIN" serve >"$HOME_DIR/ollama.log" 2>&1 &
  echo $! >"$HOME_DIR/ollama.pid"
  for _ in $(seq 1 60); do curl -fs -m 2 "$OLLAMA_URL/api/version" >/dev/null 2>&1 && break; sleep 1; done
fi
got_version="$(curl -fs -m 3 "$OLLAMA_URL/api/version" | sed 's/.*"version":"\([^"]*\)".*/\1/')" || fail "ollama serve did not start, see $HOME_DIR/ollama.log"
pass "ollama $got_version serving privately on $OLLAMA_URL"

# 4. Pinned weights ----------------------------------------------------------
step 4/7 "Pinned weights"
mkdir -p "$HOME_DIR/gguf"
gguf="$HOME_DIR/gguf/$GGUF_FILE"
have_model="$(curl -fs "$OLLAMA_URL/api/tags" | grep -c "$MODEL_DIGEST" || true)"
if [[ "$have_model" != "0" ]]; then
  pass "pinned model already built, GGUF download skipped"
elif [[ ! -f "$gguf" || "$(sha256_of "$gguf")" != "$GGUF_SHA256" ]]; then
  curl -fsSL --retry 5 --retry-delay 2 -A "asin-hhc-join" -o "$gguf.part" "$GGUF_URL"
  mv "$gguf.part" "$gguf"
fi
if [[ "$have_model" == "0" ]]; then
  [[ "$(sha256_of "$gguf")" == "$GGUF_SHA256" ]] || fail "GGUF sha256 mismatch (expected ${GGUF_SHA256:0:12})"
  pass "GGUF sha256 ${GGUF_SHA256:0:12}"
fi

# 5. Build and check the pinned model ----------------------------------------
step 5/7 "Model $MODEL_TAG"
if [[ -n "$SOURCE" ]]; then cp "$SOURCE/gpu-mesh/models/asin-qwen0.5b.Modelfile" "$HOME_DIR/gguf/Modelfile"
else curl -fsSL "$REPO_RAW/$REF/gpu-mesh/models/asin-qwen0.5b.Modelfile" -o "$HOME_DIR/gguf/Modelfile"; fi
if [[ "$have_model" == "0" ]]; then
  (cd "$HOME_DIR/gguf" && OLLAMA_HOST="127.0.0.1:${PORT}" "$OLLAMA_BIN" create "$MODEL_NAME" -f Modelfile >"$HOME_DIR/create.log" 2>&1) || { tail -5 "$HOME_DIR/create.log" >&2; fail "ollama create failed"; }
  rm -f "$gguf"   # Ollama keeps its own copy of the weights blob
fi
actual="$(curl -fs "$OLLAMA_URL/api/tags" | MT="$MODEL_TAG" "$VPY" -c 'import json,os,sys
for m in json.load(sys.stdin).get("models") or []:
    if (m.get("name") or m.get("model")) == os.environ["MT"]: print(m.get("digest","")); break' 2>/dev/null || true)"
if [[ "$actual" != "$MODEL_DIGEST" ]]; then
  echo "  expected digest $MODEL_DIGEST" >&2
  echo "  actual digest   ${actual:-none}" >&2
  fail "manifest digest mismatch. This node could not verify anyone's work, so it was not started"
fi
pass "manifest digest ${MODEL_DIGEST:0:12} matches the mesh pin"

# 6. Compatibility check -----------------------------------------------------
step 6/7 "Compatibility check: replay $REF_JOB"
got_sha="$(OLLAMA_URL="$OLLAMA_URL" MT="$MODEL_TAG" RP="$REF_PROMPT" RS="$REF_SEED" "$VPY" - <<'PYC'
import hashlib, json, os, urllib.request
from gpumesh_node.runtime import ollama_payload
job = {"model": os.environ["MT"], "messages": [{"role": "user", "content": os.environ["RP"]}],
       "seed": int(os.environ["RS"]), "temperature": 0, "max_tokens": 16,
       "top_k": 1, "top_p": 1.0, "repeat_penalty": 1.0, "num_ctx": 2048}
body = ollama_payload(job)
body["stream"] = False
req = urllib.request.Request(os.environ["OLLAMA_URL"] + "/api/chat", data=json.dumps(body).encode(),
                             headers={"content-type": "application/json"})
with urllib.request.urlopen(req, timeout=300) as resp:
    text = json.load(resp)["message"]["content"]
print(hashlib.sha256(text.encode("utf-8")).hexdigest())
PYC
)" || fail "reference replay did not run, see $HOME_DIR/ollama.log"
if [[ "$got_sha" != "$REF_OUTPUT_SHA" ]]; then
  echo "  expected output sha256 $REF_OUTPUT_SHA" >&2
  echo "  actual output sha256   $got_sha" >&2
  fail "this machine does not reproduce the mesh reference output, so it would disagree with honest work. Not started. Please open an issue with this output"
fi
pass "output sha256 ${REF_OUTPUT_SHA:0:12} matches the worker and first verifier of $REF_JOB"

# 7. Register and run --------------------------------------------------------
step 7/7 "Register and run"
umask 077
cat >"$HOME_DIR/stop.sh" <<STOP
#!/usr/bin/env bash
[[ -f "$HOME_DIR/node.pid" ]] && kill "\$(cat "$HOME_DIR/node.pid")" 2>/dev/null
[[ -f "$HOME_DIR/ollama.pid" ]] && kill "\$(cat "$HOME_DIR/ollama.pid")" 2>/dev/null
rm -f "$HOME_DIR/node.pid" "$HOME_DIR/ollama.pid"; echo "stopped"
STOP
chmod 700 "$HOME_DIR/stop.sh"
args=(-m gpumesh_node --coordinator "$COORD" --name "$NAME" --backend ollama
      --ollama-host "$OLLAMA_URL" --state "$HOME_DIR/node.json" --job-timeout 300)
[[ -n "$PAYOUT" ]] && args+=(--payout-address "$PAYOUT")
if [[ "$FOREGROUND" == "1" ]]; then
  echo "  running in the foreground, Ctrl-C to stop"
  exec "$VPY" "${args[@]}"
fi
[[ -f "$HOME_DIR/node.pid" ]] && kill "$(cat "$HOME_DIR/node.pid")" 2>/dev/null || true
PYTHONUNBUFFERED=1 nohup "$VPY" "${args[@]}" >>"$HOME_DIR/node.log" 2>&1 &
echo $! >"$HOME_DIR/node.pid"
node_id=""
for _ in $(seq 1 45); do
  if [[ -s "$HOME_DIR/node.json" ]]; then
    node_id="$("$VPY" -c 'import json,sys;print(json.load(open(sys.argv[1])).get("node_id",""))' "$HOME_DIR/node.json" 2>/dev/null || true)"
    [[ -n "$node_id" ]] && break
  fi
  kill -0 "$(cat "$HOME_DIR/node.pid")" 2>/dev/null || { tail -20 "$HOME_DIR/node.log" >&2; fail "worker exited, log above"; }
  sleep 1
done
[[ -n "$node_id" ]] || { tail -20 "$HOME_DIR/node.log" >&2; fail "worker did not register within 45 s"; }
chmod 600 "$HOME_DIR/node.json"
pass "registered $node_id as $NAME (token saved in $HOME_DIR/node.json, mode 600)"

if [[ "$SMOKE" == "1" ]]; then
  echo "  sending one public test request so there is work to do"
  curl -sS -m 70 -o "$HOME_DIR/smoke.json" -w '  smoke request http %{http_code}\n' \
    -H 'content-type: application/json' -H 'x-gpumesh-wait-seconds: 55' \
    -d "{\"model\":\"$MODEL_TAG\",\"messages\":[{\"role\":\"user\",\"content\":\"In one sentence, what is a hash?\"}],\"max_tokens\":48}" \
    "$COORD/v1/chat/completions" || true
fi

cat <<DONE

You are on the mesh.
  node        $node_id ($NAME)
  status      $COORD/api/stats   (look for your node id)
  proof       https://dbottrader.github.io/Holbrook-CP8-HHC/proof/
  logs        tail -f $HOME_DIR/node.log
  stop        bash $HOME_DIR/stop.sh
Your node now claims jobs for $MODEL_TAG and replays other nodes' jobs as a verifier.
A job settles on Base Sepolia after two distinct verifiers, neither of them the worker, agree.
HHC is a utility credit for verified contribution. It is not sold and pays no return.
DONE
