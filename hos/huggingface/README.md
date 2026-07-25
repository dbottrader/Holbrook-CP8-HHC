---
language:
- en
license: mit
library_name: transformers
pipeline_tag: text-generation
tags:
- asin-hhc
- cp8
- geometric-intelligence
- gpt2
- architecture
- untrained
- research-preview
---

# ASIN-HHC CP8 Geometric Transformer — Architecture E0

This is a machine-readable reconstruction target for a 12-layer, 12-head, 768-dimensional GPT-2-class model with a 512-token context window and a target vocabulary of 1,024 geometric/glyph tokens.

**No trained weights or canonical tokenizer are included. The package is not inference-ready.**

Run `python build_untrained_reference.py` only to verify that the configuration can instantiate a randomly initialized model.
