# CP8 Replay Specimen — what I actually ran, 2026-10-07

**Executor:** Ace, on Dennis Christie's workspace.
**Rule, as before:** this report describes evidence; it does not promote evidence. Promoted/ESTABLISHED findings after all runs below: **still 0.** Everything remains `HOLD`, now with executable receipts instead of narratives.

You asked me to impress you with the data on hand. So I didn't write another essay. I found the code, ran it, broke it, reproduced its results, and built the missing CCD-9 test harness. Here is the receipt trail.

---

## 1. The code exists — in Drive, exactly where STATUS.md said

`cp8-morphology-v1.0.0.zip`, Google Drive, modified 2026-08-08.
- 40,329 bytes (STATUS.md said 39.4 KB — matches)
- SHA-256: `26a9237898aaa50a04bfdaf265a00dd7a630f2e7faa35cb7dfe18347579fb972`
- Contents: 7 Python modules (`geometry, graph, binary, fingerprint, synthetic, pipeline, cli`), `setup.py`, `requirements.txt`, README/LICENSE — and the recorded `examples/crabwood_face_genome.json` (128 circles, 2,197 outline points, evidence 0.669).

I downloaded it read-only, hashed every file inside, and inspected the code before running it (no network, shell, eval, or destructive calls — file writes only to output paths).

## 2. First honest result: the package does not import as shipped

```
import cp8_morphology
→ ModuleNotFoundError: No module named 'cp8_cropcircle_processor'
```

Cause: `pipeline.py` imports stale names (`cp8_cropcircle_processor`, `cp8_graph`, `cp8_binary`, `cp8_fingerprint`) and `__init__.py` imports `run_pipeline` / `GeometryEngine` / `analyze_image`, while the shipped modules are `geometry/graph/binary/fingerprint` with `CropCircleEngine` / `analyze_crop_circle` / `run_full_pipeline`.

**But** every individual module imports and executes cleanly. So I wired the modules directly in my own harness — without modifying your code — and ran everything below that way. The repair is a one-file wiring fix plus a smoke test; I did not publish a modified version of your proprietary code.

## 3. Crabwood genome: Pass 2/3/5 recompute exactly

I fed the zip's recorded Crabwood measurements back through your graph, binary, and fingerprint code:

| Metric | Recorded | Recomputed | Match |
|---|---|---|---|
| Graph nodes / edges | 128 / 224 | 128 / 224 | exact |
| Clustering coefficient | 0.2536 | 0.2536 | exact |
| Density | 0.027559 | 0.027559 | exact |
| Spectral gap | 0.000451 | 0.000451 | exact |
| Binary surviving rules | 1 (`filled_empty_grid`) | 1 (`filled_empty_grid`) | exact |
| Outline box dimension | 1.2293 ± 0.0433, R² 0.9951 | 1.2293 ± 0.0433, R² 0.9951 | exact |

Environment here was OpenCV 5.0 / NumPy 2.5.3 / scikit-image 0.26, versus the genome's recorded OpenCV 4.12 / NumPy 2.2.5 — the metrics are stable across that drift.

Boundary: this reproduces Pass 2/3/5 *from recorded measurements*. Pass 0–1 image detection cannot be replayed yet, because the original input (`2289.png` in the genome provenance) is in neither the zip nor any public repo.

## 4. The negative control reproduces — 5 of 6, again

I generated your synthetic control library with your `synthetic.py`, then ran each image through the full chain (geometry → graph → binary → fingerprint):

| Control | Circles (recorded → mine) | Box dim (recorded → mine) | Binary triggered? |
|---|---|---|---|
| pack_radial_6 | 84 → 84 | 1.2594 → 1.2594 | yes |
| ifs_julia | 62 → 62 | 1.2872 → 1.2872 | yes |
| ifs_sierpinski | 57 → 53 | 0.9292 → 0.9256 | yes |
| lsys_radial | 27 → 27 | 1.0382 → 1.0382 | yes |
| grammar_default | 17 → 17 | 0.9866 → 0.9866 | yes |
| lsys_koch | 0 → 0 | none → none | no |

**5/6 synthetic controls trigger binary detection, all via `filled_empty_grid`** — exactly your recorded critical finding, now independently reproduced by execution. (The one numeric drift, sierpinski, is consistent with the OpenCV/scikit-image version gap; I recorded it rather than hiding it.)

This is the most important result in the package. Your own conclusion stands, and is now backed by a rerun: *Pass 3 cannot support message-encoding claims until the same rule must survive on ≥3 independent formations.*

## 5. Holbrook evidence infrastructure: runs green

Using the public repo files directly:
- `dar_p/gate_validator.py` test suite: **8 passed**
- `scripts/build-merkle.py` → `scripts/verify.py` on a test tree: **exit 0 — ALL CHECKS PASSED, 4/4 files, Merkle root VALID, HOS hash VALID, combined signature VALID**

So the receipt/verification layer isn't just specified — it executes, today, on a clean checkout.

## 6. CCD-9: I built the missing harness and validated the method

Your original scan code, seed, and frozen image aren't public, so the original h15 measurement still cannot be replayed — that blocker is unchanged and I won't pretend otherwise.

What I could do: a clean-room implementation of the recorded method (polar angular scan, 1440 × 8 sampling, harmonics 1–30, centre `[310, 205]`, ellipse `[190, 130]`, fixed seed `20261007`, recorded in the output), run on synthetic controls:

| Synthetic case | Top harmonic | h15 permutation null |
|---|---|---|
| 15-fold wheel | **15** (0.5564) | p at floor (≈0.0005, 2,000 perms) |
| 8-fold wheel | 8 (0.5987) | p = 0.98 |
| 3 concentric rings | 2 (0.8198) | p = 0.97 |
| Random blobs | 4 (0.2632) | p = 0.80 |

The method discriminates exactly as it should: it finds 15 in a 15-fold image and does not invent 15 in 8-fold, ring, or random images. That makes the CCD-9 method *reconstructable and falsifiable* — a future agent now has runnable specimen code to compare against, the moment the original frozen image is hash-bound and published.

This does **not** reproduce or replace your original CCD-9 result. It validates the instrument, not the measurement.

## 7. What changed in the evidence picture

**Now executable, with receipts (this report + `CP8_REPLAY_RECEIPT_2026-10-07.json`):**
- Holbrook manifest/Merkle verification and DAR-P gate validation
- Morphology Pass 2/3/5 exact re-derivation of the Crabwood genome
- Synthetic-control battery and the Pass 3 negative-control failure
- Clean-room CCD-9 spectral method specimen

**Still blocked, unchanged:**
- Package import as shipped (one wiring fix needed)
- Pass 0–1 from the original Crabwood image (`2289.png` not published)
- Original CCD-9 replay (code/seed/frozen bytes not published)

**Promotion state: HOLD everywhere. ESTABLISHED count: 0.** The index describes evidence; it does not promote evidence — and now a good chunk of that evidence has actually been run.

---

*Local kit: `~/workspace/cp8-replay-kit/` — source zip, harness scripts, control images, spectral controls, and hashed outputs. Nothing private was published. If you want this specimen committed, say the word and I'll do it in one batched commit (receipt + report + index update) rather than a parade of approvals.*
