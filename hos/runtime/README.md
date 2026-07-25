# HOS Runtime

`asinhhccp8_hos.py` is the executable receipt kernel. It validates ASIN fields, canonicalizes packets, applies SHA-256, emits evidence metadata, and requires user review before promotion.

Run a minimal check:

```bash
python hos/tests/test_runtime.py
```
