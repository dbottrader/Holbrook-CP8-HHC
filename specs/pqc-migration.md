# NIST Post-Quantum Cryptography Migration Guide

**Version:** CP8-PQC-0.4.0  
**Protocol:** ASH-0.2  
**Standard:** NIST FIPS 203 / 204 / 205  
**HOS Ground Truth:** `63b5160ef51f0464295e86888c3e6605d8f6cc970635183887083818e8749320`

---

## Executive Summary

The Holbrook-CP8-HHC lattice is migrating to **quantum-resistant cryptography** in preparation for cryptanalytically relevant quantum computers (CRQC). This document specifies the algorithm selection, hybrid strategy, implementation roadmap, and migration timeline for all CP8 nodes.

---

## NIST-Approved Algorithms

### FIPS 203 — ML-KEM (Module Lattice-based Key Encapsulation Mechanism)

| Parameter Set | Security Level | Public Key | Secret Key | Ciphertext | Shared Secret |
|---------------|---------------|------------|------------|------------|---------------|
| ML-KEM-512    | NIST Level 1  | 800 B      | 1,632 B    | 768 B      | 32 B          |
| ML-KEM-768    | NIST Level 3  | 1,184 B    | 2,400 B    | 1,088 B    | 32 B          |
| **ML-KEM-1024** | **NIST Level 5** | **1,568 B** | **3,168 B** | **1,568 B** | **32 B** |

**CP8 Selection:** ML-KEM-768 for general use; ML-KEM-1024 for high-assurance nodes.

**Use Cases:**
- Agent-to-agent key exchange over the Distributed Soft Bus
- Encrypted `inbox/` message envelopes
- Chain-registry endpoint authentication

### FIPS 204 — ML-DSA (Module Lattice-based Digital Signature Algorithm)

| Parameter Set | Security Level | Public Key | Secret Key | Signature |
|---------------|---------------|------------|------------|-----------|
| ML-DSA-44     | NIST Level 2  | 1,312 B    | 2,560 B    | 2,420 B   |
| **ML-DSA-65** | **NIST Level 3** | **1,952 B** | **4,032 B** | **3,293 B** |
| ML-DSA-87     | NIST Level 5  | 2,592 B    | 4,896 B    | 4,595 B   |

**CP8 Selection:** ML-DSA-65 as the canonical signing algorithm.

**Use Cases:**
- Git commit attestation signatures
- Audit packet (`cp8-audit-packet.json`) agent sign-off
- Merkle root signing for build manifests
- Smart contract oracle attestation (future)

### FIPS 205 — SLH-DSA (Stateless Hash-based Digital Signature Standard)

| Parameter Set | Security Level | Public Key | Secret Key | Signature     |
|---------------|---------------|------------|------------|---------------|
| SLH-DSA-SHA2-128s | 1 | 32 B | 64 B | 7,856 B |
| **SLH-DSA-SHA2-128f** | **1** | **32 B** | **64 B** | **17,040 B** |
| SLH-DSA-SHA2-256s | 3 | 64 B | 128 B | 29,792 B |
| SLH-DSA-SHA2-256f | 5 | 64 B | 128 B | 49,856 B |

**CP8 Selection:** SLH-DSA-SHA2-128f for long-term trust-anchor signatures.

**Use Cases:**
- Root-of-trust key signing (HOS Ground Truth rotation events)
- Cold-archive Drive integrity proofs
- Genesis lattice anchor (one-time, high-assurance)

---

## Hybrid Strategy

CP8 does **not** deploy standalone PQC algorithms in production. We use a **dual-layer** approach:

```
┌─────────────────────────────────────────────┐
│  Layer 2 (PQC)  —  Future-proof             │
│  ML-KEM-768  +  ML-DSA-65  +  SLH-DSA-128f  │
├─────────────────────────────────────────────┤
│  Layer 1 (Classical)  —  Battle-tested       │
│  X25519  +  Ed25519  +  ECDSA (secp256k1)   │
└─────────────────────────────────────────────┘
```

### Rationale

1. **Conservatism:** NIST explicitly recommends hybrid deployments during transition.
2. **Performance:** Classical ops are faster; PQC provides the hedge.
3. **Interoperability:** Not all chain nodes support PQC yet.
4. **Bug-forgiveness:** If a PQC algorithm has an undiscovered weakness, the classical layer still holds.

### Hybrid Construction

**Key Encapsulation:**
```
shared_secret = SHA3-256(classical_secret || mlkem_secret)
```

**Signatures:**
```
hybrid_sig = classical_sig || ml_dsa_sig
verification = verify_classical(msg, classical_sig) AND verify_ml_dsa(msg, ml_dsa_sig)
```

---

## Implementation Status

| Component | Classical | PQC | Hybrid | Status |
|-----------|-----------|-----|--------|--------|
| Git commit signing | Ed25519 | ML-DSA-65 | Planned | 🔄 In Progress |
| Agent handshakes | X25519 | ML-KEM-768 | Planned | 📋 Backlog |
| Audit packet attestations | SHA-256 | ML-DSA-65 | Active | ✅ v0.4.0 |
| Merkle root signing | SHA-256 | ML-DSA-65 | Active | ✅ v0.4.0 |
| Chain registry auth | ECDSA | ML-DSA-65 | Planned | 📋 Backlog |
| Drive cold-archive | SHA-256 | SLH-DSA-128f | Planned | 📋 Backlog |
| Smart contract oracle | ECDSA | ML-DSA-65 | Research | 📋 Future |

---

## Migration Roadmap

### Phase 1: Capability Deployment (v0.4.0 — Now)
- ✅ ML-DSA-65 signer implemented (`verification/ml-dsa-signer.js`)
- ✅ SHA-256 verification suite hardened (`verification/verify-all.js`)
- ✅ Merkle tree calculator with inclusion proofs (`verification/verify-merkle.js`)
- 🔄 Agent keypairs generated and registered in `manifests/lattice-registry.json`

### Phase 2: Hybrid Activation (v0.5.0)
- Dual-sign all audit packets (Ed25519 + ML-DSA-65)
- Hybrid key exchange for agent handshakes
- SLH-DSA trust-anchor for genesis events

### Phase 3: PQC-First (v0.6.0)
- Default to PQC for all new operations
- Classical layer demoted to fallback
- Full chain-registry PQC migration

### Phase 4: Quantum-Safe (v1.0.0)
- Classical algorithms deprecated
- Pure PQC stack
- Formal security audit by third party

---

## Key Management

### Lattice Key Registry

All PQC keys are registered in `manifests/lattice-registry.json` with:
- `fingerprint`: SHA-256(public_key)[0:16]
- `algorithm`: ML-DSA-65 / ML-KEM-768 / SLH-DSA-128f
- `agent_id`: Which agent owns this key
- `created`: ISO-8601 timestamp
- `rotation_policy`: `auto-90d` or `manual`

### Storage
- **Secret keys:** Local vault only (`verification/ml-dsa-key.json`), never committed
- **Public keys:** Committed to repo for transparency
- **Rotation:** 90-day auto-rotation for operational keys; manual rotation for trust anchors

---

## Security Parameters

| Threat Model | Defense |
|-------------|---------|
| Harvest-now-decrypt-later | Hybrid encryption active immediately |
| Signature forgery (quantum) | ML-DSA-65 + classical dual-sig |
| Key compromise | 90-day rotation + lattice registry |
| Algorithm weakness | Hybrid design; if one fails, the other holds |
| Side-channel | Constant-time implementations via `@noble/post-quantum` |

---

## References

1. NIST FIPS 203 — *Module-Lattice-Based Key-Encapsulation Mechanism Standard*, 2024
2. NIST FIPS 204 — *Module-Lattice-Based Digital Signature Standard*, 2024
3. NIST FIPS 205 — *Stateless Hash-Based Digital Signature Standard*, 2024
4. [pq-crystals.org](https://pq-crystals.org) — CRYSTALS-Kyber / CRYSTALS-Dilithium reference
5. [noble-post-quantum](https://github.com/paulmillr/noble-post-quantum) — Implementation library
6. Holbrook `verification/ml-dsa-signer.js` — CP8 canonical signer

---

*"The lattice that withstands quantum scrutiny is the lattice that endures."*

**End of PQC Migration Guide v0.4.0**
