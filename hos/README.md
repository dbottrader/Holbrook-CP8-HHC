# ASIN-HHC-CP8 / HOS Full-Stack Release

This directory consolidates the executable HOS reference runtime, optional Supabase persistence, Hugging Face-compatible CP8 E0 architecture package, deployment scaffolding, and the Ace operating prompt.

## Evidence boundary

- **HOS runtime:** executable reference implementation.
- **Supabase:** optional persistence adapter and schema; credentials are not included.
- **Hugging Face:** E0 architecture/reconstruction package only. No trained weights or canonical tokenizer are included.
- **Ace prompt:** operating instructions for structured ASIN processing and receipt generation; it does not grant external authority or prove autonomous execution.

## Core rule

> No mechanism may silently convert uncertainty into authority.

## Layout

- `runtime/` — deterministic ASIN packet and receipt engine.
- `api/` — FastAPI service exposing health, process, receipt, and manifest endpoints.
- `supabase/` — SQL schema and safe environment template.
- `huggingface/` — GPT-2-class CP8 E0 configuration and reconstruction utility.
- `deploy/` — container deployment files.
- `prompts/` — Ace/HOS operating instructions.
- `provenance/` — release manifest and evidence status.

## Local run

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r hos/api/requirements.txt
uvicorn hos.api.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.
