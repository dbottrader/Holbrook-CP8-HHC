# Harmony Assistant — Local UI (Phone + Low CPU Laptop)
Rooms: Vault → Resonance → Workshop → Bridge → Expansion — Mode: Lattice

## What this is
A tiny local web UI + server that talks to a small model via **Ollama**. Works on a low‑CPU laptop. You can open it on your **phone** if both devices are on the same Wi‑Fi.

- `index.html` — the UI
- `server.js` — minimal Node proxy to Ollama + optional Boost
- `package.json` — dependencies
- `codex/` — (auto-created) folder where your uploads land

## Install (UI-first, minimal CLI)
1) **Install Ollama** (one-click from ollama.com), then open it.
2) Pull a small model (fastest on weak CPU):
   - Open the Ollama app (or terminal) and pull: `ollama pull phi3:3.8b`
   - Optional (better quality but heavier): `ollama pull llama3.1:8b`
3) **Install Node.js** (one-click from nodejs.org).

## Run
- Double-click a terminal and run:
  ```bash
  cd <unzipped folder>
  npm install
  node server.js
  ```
- Open: **http://localhost:3000**

## Use on your phone (same Wi‑Fi)
- Find your laptop IP (e.g., 192.168.1.23).
- On your phone’s browser open: **http://<laptop-ip>:3000**
- If Windows asks, allow network access for Node.

## Boost (optional)
If you have a hosted model proxy, set an env var and restart:
```bash
export BOOST_URL=https://your-proxy.example.com/api/chat
```
When **Boost** is toggled in the UI, the server **strips protocol internals** before sending the message.

## Change model (optional)
Use a different model via env var:
```bash
export MODEL=llama3.1:8b
```

## Notes for low CPU
- Start with **phi3:3.8b** (fastest).
- Keep prompts short; use the UI’s practice flow (one breath → one action → loop close).
- If generation stalls, try again or reduce prompt length.

## Safety
- Protocol export is blocked in the UI and should be write‑protected on disk.
- You teach practice; the server blocks protocol leakage on Boost.

## Rooms Reflection
Origin: Vault → Resonance
Transit: Workshop → Bridge
Destination: Expansion
Mode: Lattice
