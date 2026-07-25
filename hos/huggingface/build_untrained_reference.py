from pathlib import Path

from transformers import GPT2Config, GPT2LMHeadModel

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "cp8-reference-init"

config = GPT2Config.from_json_file(str(ROOT / "config.json"))
model = GPT2LMHeadModel(config)
model.save_pretrained(OUT, safe_serialization=True)
print(f"Wrote randomly initialized reference model to {OUT}")
print("This is not a trained CP8 checkpoint.")
