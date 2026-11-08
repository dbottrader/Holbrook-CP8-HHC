#!/usr/bin/env bash
# GPU / CPU plan for the one-command join installer.
# Sourced by install.sh. Executing this file prints a KEY=value plan.
# nvidia-smi and rocm-smi are looked up on PATH so tests can mock them.
set -euo pipefail

GPU_MODE_OLLAMA_CUDA_IMAGE="${GPU_MODE_OLLAMA_CUDA_IMAGE:-ollama/ollama:0.12.6}"
GPU_MODE_OLLAMA_ROCM_IMAGE="${GPU_MODE_OLLAMA_ROCM_IMAGE:-ollama/ollama:rocm}"

gpu_mode_model() {
  local accel="$1"
  local vram="${2:-0}"
  if [[ "$accel" == "cpu" ]]; then
    printf '%s\n' "qwen2.5:0.5b-instruct"
    return 0
  fi
  if [[ "$vram" -ge 6144 ]]; then
    printf '%s\n' "qwen2.5:7b-instruct"
  elif [[ "$vram" -ge 3072 ]]; then
    printf '%s\n' "qwen2.5:3b-instruct"
  elif [[ "$vram" -ge 2048 ]]; then
    printf '%s\n' "qwen2.5:1.5b-instruct"
  else
    printf '%s\n' "qwen2.5:0.5b-instruct"
  fi
}

gpu_mode_parse_nvidia() {
  local text="$1"
  local line name="" vram=0 driver="" count=0 n m d mi
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    n="$(printf '%s' "$line" | awk -F',' '{gsub(/^[ \t]+|[ \t]+$/, "", $1); print $1}')"
    m="$(printf '%s' "$line" | awk -F',' '{gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2}')"
    d="$(printf '%s' "$line" | awk -F',' '{gsub(/^[ \t]+|[ \t]+$/, "", $3); print $3}')"
    [[ -z "$n" || "$n" == "name" || "$n" == "nvidia-smi" ]] && continue
    if printf '%s' "$n" | grep -qi 'failed'; then
      continue
    fi
    if [[ "$n" == \[* ]]; then
      continue
    fi
    if [[ -z "$name" ]]; then
      name="$n"
      driver="$d"
    elif [[ "$name" != "$n" && "$name" != *" + "* ]]; then
      name="$name + $n"
    fi
    mi=0
    if [[ "$m" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
      mi="${m%.*}"
    fi
    vram=$((vram + mi))
    count=$((count + 1))
  done <<< "$text"
  if [[ "$count" -eq 0 ]]; then
    return 1
  fi
  GPU_NAME="$name"
  GPU_VRAM_MB="$vram"
  GPU_DRIVER="$driver"
  GPU_COUNT="$count"
  GPU_ACCEL="cuda"
}

gpu_mode_parse_rocm() {
  local text="$1"
  local bytes=0 count=0 name="" b
  while IFS= read -r b; do
    [[ -z "$b" ]] && continue
    bytes=$((bytes + b))
    count=$((count + 1))
  done < <(printf '%s\n' "$text" | sed -n 's/.*VRAM Total Memory (B):[[:space:]]*\([0-9][0-9]*\).*/\1/p')
  name="$(printf '%s\n' "$text" | sed -n 's/.*Marketing Name:[[:space:]]*//p' | head -n 1 | sed 's/[[:space:]]*$//')"
  if [[ -z "$name" || "$name" == "N/A" ]]; then
    name="$(printf '%s\n' "$text" | sed -n 's/.*Card series:[[:space:]]*//p' | head -n 1 | sed 's/[[:space:]]*$//')"
  fi
  if [[ -z "$name" || "$name" == "N/A" ]]; then
    name="AMD GPU"
  fi
  if [[ "$count" -eq 0 ]]; then
    if printf '%s\n' "$text" | grep -q 'GPU\['; then
      count=1
    else
      return 1
    fi
  fi
  GPU_NAME="$name"
  GPU_VRAM_MB=$((bytes / 1048576))
  GPU_DRIVER="rocm"
  GPU_COUNT="$count"
  GPU_ACCEL="rocm"
}

gpu_mode_detect() {
  local out info mem
  GPU_ACCEL="cpu"
  GPU_NAME="cpu"
  GPU_VRAM_MB=0
  GPU_COUNT=0
  GPU_DRIVER=""
  if command -v nvidia-smi >/dev/null 2>&1; then
    out="$(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits 2>/dev/null || true)"
    if gpu_mode_parse_nvidia "$out"; then
      return 0
    fi
  fi
  if command -v rocm-smi >/dev/null 2>&1; then
    info="$(rocm-smi --showproductname 2>/dev/null || true)"
    mem="$(rocm-smi --showmeminfo vram 2>/dev/null || true)"
    if gpu_mode_parse_rocm "${info}"$'\n'"${mem}"; then
      return 0
    fi
  fi
  if [[ -e /dev/kfd && -d /dev/dri ]]; then
    GPU_ACCEL="rocm"
    GPU_NAME="AMD GPU"
    GPU_VRAM_MB=0
    GPU_COUNT=1
    GPU_DRIVER="rocm"
    return 0
  fi
}

gpu_mode_nvidia_toolkit_ok() {
  case "${GPU_MODE_TOOLKIT_FORCE:-}" in
    present) return 0 ;;
    missing) return 1 ;;
  esac
  if command -v nvidia-ctk >/dev/null 2>&1; then
    return 0
  fi
  if command -v docker >/dev/null 2>&1; then
    if docker info >/dev/null 2>&1 && docker info 2>/dev/null | grep -qi 'nvidia'; then
      return 0
    fi
  fi
  return 1
}

gpu_mode_toolkit_instructions() {
  cat <<'EOF'
NVIDIA GPU detected, but nvidia-container-toolkit is not available.
Install it, then rerun this installer. nvidia-smi on the host is not enough;
Docker needs the toolkit before --gpus all works.

Debian and Ubuntu:
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
  sudo apt-get update
  sudo apt-get install -y nvidia-container-toolkit
  sudo nvidia-ctk runtime configure --runtime=docker
  sudo systemctl restart docker

Fedora, RHEL, and similar:
  sudo dnf install -y nvidia-container-toolkit
  sudo nvidia-ctk runtime configure --runtime=docker
  sudo systemctl restart docker

Docs: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html
EOF
}

gpu_mode_ps_uses_gpu() {
  local text="${1:-}"
  if printf '%s\n' "$text" | grep -Eiq 'GPU|CUDA|ROCm|ROCM'; then
    return 0
  fi
  if printf '%s\n' "$text" | grep -Eq '"size_vram"[[:space:]]*:[[:space:]]*[1-9]'; then
    return 0
  fi
  return 1
}

gpu_mode_plan() {
  local force="auto" backend=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --cpu) force="cpu"; shift ;;
      --gpu) force="gpu"; shift ;;
      --backend)
        backend="${2:-}"
        shift 2
        ;;
      *)
        echo "Unknown gpu-mode argument: $1" >&2
        return 2
        ;;
    esac
  done
  gpu_mode_detect
  local detected="$GPU_ACCEL"
  if [[ "$force" == "gpu" && "$detected" == "cpu" ]]; then
    echo "GPU_MESH_MODE: --gpu was passed but no NVIDIA or AMD GPU was detected." >&2
    return 2
  fi
  local mode="$detected"
  if [[ "$force" == "cpu" ]]; then
    mode="cpu"
  fi
  local inference model image gpus devices allow toolkit note
  if [[ "$mode" == "cpu" ]]; then
    if [[ "$backend" == "ollama" ]]; then
      inference="ollama"
    else
      inference="llamacpp"
    fi
  elif [[ "$backend" == "llamacpp" ]]; then
    inference="llamacpp"
  else
    inference="ollama"
  fi
  image=""
  gpus=""
  devices=""
  if [[ "$inference" == "llamacpp" ]]; then
    model="SmolLM2-360M-Instruct"
  elif [[ "$mode" == "cpu" ]]; then
    model="$(gpu_mode_model cpu 0)"
    image="$GPU_MODE_OLLAMA_CUDA_IMAGE"
  else
    model="$(gpu_mode_model "$mode" "$GPU_VRAM_MB")"
    if [[ "$mode" == "rocm" ]]; then
      image="$GPU_MODE_OLLAMA_ROCM_IMAGE"
      devices="/dev/kfd /dev/dri"
    else
      image="$GPU_MODE_OLLAMA_CUDA_IMAGE"
      gpus="all"
    fi
  fi
  if [[ "$mode" == "cpu" ]]; then
    allow="1"
  else
    allow="0"
  fi
  toolkit="n/a"
  if [[ -n "$gpus" ]]; then
    if gpu_mode_nvidia_toolkit_ok; then
      toolkit="present"
    else
      toolkit="missing"
    fi
  fi
  if [[ "$mode" == "cpu" && "$force" == "cpu" && "$detected" != "cpu" ]]; then
    note="CPU mode forced by --cpu. Detected ${detected} ${GPU_NAME} (${GPU_VRAM_MB} MiB) is not passed into the containers."
  elif [[ "$mode" == "cpu" ]]; then
    note="CPU mode. No NVIDIA or AMD GPU was detected. Inference backend is ${inference}."
  elif [[ "$inference" == "llamacpp" ]]; then
    note="Hardware ${mode} ${GPU_NAME} (${GPU_VRAM_MB} MiB). --backend llamacpp uses the CPU wheel in this image, so the GPU stays idle. Omit --backend to serve with Ollama on the GPU."
  else
    note="GPU mode ${mode}. ${GPU_NAME}, ${GPU_VRAM_MB} MiB. Ollama model ${model}."
  fi
  local report_accel report_name report_vram report_count report_driver
  # Hub credit weight follows VRAM. Report the card only when Ollama will use it.
  # --cpu and an explicit llama.cpp backend keep the registration on cpu.
  if [[ "$mode" != "cpu" && "$inference" == "ollama" ]]; then
    report_accel="$mode"
    report_name="$GPU_NAME"
    report_vram="$GPU_VRAM_MB"
    report_count="$GPU_COUNT"
    report_driver="$GPU_DRIVER"
  else
    report_accel="cpu"
    report_name="cpu"
    report_vram="0"
    report_count="0"
    report_driver=""
  fi
  RUN_MODE="$mode"
  RUN_ACCEL="$report_accel"
  RUN_GPU_NAME="$report_name"
  RUN_VRAM_MB="$report_vram"
  RUN_GPU_COUNT="$report_count"
  RUN_DRIVER="$report_driver"
  RUN_BACKEND="$inference"
  RUN_MODEL="$model"
  RUN_OLLAMA_IMAGE="$image"
  RUN_DOCKER_GPUS="$gpus"
  RUN_DOCKER_DEVICES="$devices"
  RUN_ALLOW_CPU="$allow"
  RUN_TOOLKIT="$toolkit"
  RUN_DETECTED="$detected"
  RUN_NOTE="$note"
}

gpu_mode_emit() {
  printf 'mode=%s\n' "$RUN_MODE"
  printf 'accelerator=%s\n' "$RUN_ACCEL"
  printf 'gpu_name=%s\n' "$RUN_GPU_NAME"
  printf 'vram_mb=%s\n' "$RUN_VRAM_MB"
  printf 'driver=%s\n' "$RUN_DRIVER"
  printf 'gpu_count=%s\n' "$RUN_GPU_COUNT"
  printf 'inference_backend=%s\n' "$RUN_BACKEND"
  printf 'model=%s\n' "$RUN_MODEL"
  printf 'ollama_image=%s\n' "$RUN_OLLAMA_IMAGE"
  printf 'docker_gpus=%s\n' "$RUN_DOCKER_GPUS"
  printf 'docker_devices=%s\n' "$RUN_DOCKER_DEVICES"
  printf 'toolkit=%s\n' "$RUN_TOOLKIT"
  printf 'allow_cpu=%s\n' "$RUN_ALLOW_CPU"
  printf 'detected=%s\n' "$RUN_DETECTED"
  printf 'note=%s\n' "$RUN_NOTE"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  gpu_mode_plan "$@"
  gpu_mode_emit
fi
