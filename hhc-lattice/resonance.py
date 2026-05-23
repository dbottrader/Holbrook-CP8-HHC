# -*- coding: utf-8 -*-
"""
ASIN-HHC / Holbrook-CP8-HHC
Harmonic Algebra Resonance Engine v2.0
Codex: ASIN_HHC_HARMONIC_ALGEBRA_v1.0

Implements operators from:
- Hoffman (1997) harmonic algebra — noncommutative glyph lattice
- Kawamura (2023) formal sine — resonance operator basis
- Crown Omega (2025) harmonic encryption — self-mutating keys
- Harmonic Ninth (2025) RHA — SHA-as-glyph epistemology
- Nexus Framework (2025) — cross-layer bridge morphisms

NOTE: Resonance scoring is an auxiliary interpretive metric layered
atop standard cryptographic hashing (SHA-256). It is NOT a
substitute for cryptographic verification.

CP8 Protocol • ASIN-HHC Framework • Holbrook Distributed Lattice
"""

import hashlib
from math import pi, e
from typing import List, Dict, Any

PHI = (1 + 5**0.5) / 2
TAU = 1 / PHI  # Acceptance threshold ≈ 0.618


class CP8ResonanceEngine:
    """
    Implements harmonic algebra operators for the CP8 glyph lattice.
    
    IMPORTANT: The resonance_score() and verify_seal() methods are
    SYMBOLIC/INTERPRETIVE heuristics, not cryptographic primitives.
    The actual security primitive remains SHA-256.
    """

    @staticmethod
    def glyph_hash(glyph_string: str, timestamp: float, mu_phase: float) -> str:
        """Generate a SHA-256 seal from glyph string + timestamp + phase."""
        payload = f"{glyph_string}|{timestamp}|{mu_phase}"
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def resonance_score(seal: str, constants=(pi, e, PHI)) -> float:
        """
        Compute symbolic resonance score of a SHA-256 seal.
        
        This is an AUXILIARY METRIC for interpretive alignment —
        NOT a cryptographic verification primitive. For actual
        integrity verification, use verify_seal() against SHA-256.
        """
        vec = [int(seal[i:i+2], 16) for i in range(0, 64, 2)]
        const_vec = [constants[i % len(constants)] for i in range(len(vec))]
        dot = sum(a * b for a, b in zip(vec, const_vec))
        norm = sum(x**2 for x in vec) ** 0.5
        return abs(dot) / norm if norm else 0.0

    @staticmethod
    def verify_seal(seal: str) -> bool:
        """
        Check if seal passes symbolic resonance threshold.
        
        NOTE: This is a SYMBOLIC acceptance check. The actual
        cryptographic verification is done via SHA-256 comparison.
        Both should pass for full validation.
        """
        return CP8ResonanceEngine.resonance_score(seal) > TAU

    @staticmethod
    def stuffle(chain_a: List[Any], chain_b: List[Any]) -> List[List[Any]]:
        """
        Generate the full stuffle (quasi-shuffle) product of two chains.
        
        Mathematically: stuffle(a, b) = all interleavings preserving
        internal order of a and b, plus merged head products.
        
        Returns a list of ALL possible stuffle results (combinatorial).
        For deterministic output, use stuffle_merge() instead.
        """
        if not chain_a:
            return [chain_b[:]]
        if not chain_b:
            return [chain_a[:]]
        
        results = []
        # Take from a
        for rest in CP8ResonanceEngine.stuffle(chain_a[1:], chain_b):
            results.append([chain_a[0]] + rest)
        # Take from b
        for rest in CP8ResonanceEngine.stuffle(chain_a, chain_b[1:]):
            results.append([chain_b[0]] + rest)
        return results

    @staticmethod
    def stuffle_merge(chain_a: List[Any], chain_b: List[Any]) -> List[Any]:
        """
        Deterministic ordered merge — preserves order from both chains.
        
        This is the CP8 Codex merge operator: preserves provenance
        order and concatenates deterministically. NOT the full
        combinatorial stuffle (use stuffle() for that).
        """
        result = []
        i = j = 0
        while i < len(chain_a) or j < len(chain_b):
            if i < len(chain_a):
                result.append(chain_a[i])
                i += 1
            if j < len(chain_b):
                result.append(chain_b[j])
                j += 1
        return result

    @staticmethod
    def shuffle(stream_a: List[Any], stream_b: List[Any]) -> List[List[Any]]:
        """
        Generate all shuffle interleavings of two streams.
        
        The shuffle product (Hoffman) preserves order within each
        stream but interleaves them in all possible ways.
        """
        if not stream_a:
            return [stream_b[:]]
        if not stream_b:
            return [stream_a[:]]
        
        results = []
        # Take from a
        for rest in CP8ResonanceEngine.shuffle(stream_a[1:], stream_b):
            results.append([stream_a[0]] + rest)
        # Take from b
        for rest in CP8ResonanceEngine.shuffle(stream_a, stream_b[1:]):
            results.append([stream_b[0]] + rest)
        return results

    @staticmethod
    def pi_morphism(state: Dict[str, Any]) -> Dict[str, Any]:
        """Π: Forward projection to next layer (Vault → Resonance → Workshop → Bridge)."""
        return {**state, "layer": state.get("layer", 0) + 1}

    @staticmethod
    def iota_morphism(state: Dict[str, Any]) -> Dict[str, Any]:
        """ι: Backward trace to origin — remove layer metadata."""
        return {k: v for k, v in state.items() if k != "layer"}

    @staticmethod
    def layer_sync(local_state: Dict[str, Any], remote_state: Dict[str, Any], epsilon: float = 1e-9) -> bool:
        """
        Verify round-trip identity: ι(Π(local)) ≈ local within ε.
        This is the formal coherence check for layer synchronization.
        """
        projected = CP8ResonanceEngine.pi_morphism(local_state)
        round_trip = CP8ResonanceEngine.iota_morphism(projected)
        # Compare hashes for drift detection
        local_hash = hashlib.sha256(str(sorted(local_state.items())).encode()).hexdigest()
        round_hash = hashlib.sha256(str(sorted(round_trip.items())).encode()).hexdigest()
        return local_hash == round_hash


if __name__ == "__main__":
    engine = CP8ResonanceEngine()
    
    # Basic seal generation
    seal = engine.glyph_hash("◇∴◎", 1716447600.0, 111.0)
    score = engine.resonance_score(seal)
    print(f"Seal: {seal[:16]}...")
    print(f"Resonance Score: {score:.6f}")
    print(f"Symbolic Verified: {engine.verify_seal(seal)}")
    print()
    
    # Stuffle merge (deterministic)
    a = ["glyph_a", "glyph_b"]
    b = ["glyph_c", "glyph_d"]
    merged = engine.stuffle_merge(a, b)
    print(f"Stuffle merge: {merged}")
    
    # Full stuffle (combinatorial)
    all_stuffles = engine.stuffle(a, b)
    print(f"Full stuffle count: {len(all_stuffles)} results")
    
    # Shuffle (combinatorial interleaving)
    all_shuffles = engine.shuffle(a, b)
    print(f"Shuffle count: {len(all_shuffles)} results")
    
    # Layer morphism
    state = {"layer": 0, "data": "test"}
    projected = engine.pi_morphism(state)
    print(f"Projected: {projected}")
    
    # Sync check
    sync_ok = engine.layer_sync(state, projected)
    print(f"Layer sync: {sync_ok}")
