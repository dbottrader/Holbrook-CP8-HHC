"""
ANU-28 Reference Interpreter v1.1

Purpose:
    Parse ANU-28 glyph packets into deterministic, auditable, plain-language
    AI coordination instructions.

Changes from v1.0:
    - Loads glyph definitions from anu28_registry.json when available.
    - Reports unknown glyphs instead of silently ignoring them.
    - Adds structured constraint merging with conflict reporting.
    - Emits a Universal Object style output with evidence_level,
      governance_state, source_glyphs, constraints, warnings, and compiled prompt.
    - Preserves strict non-claims: glyphs are semantic operators only.

Usage:
    python reference_interpreter_v1_1.py

Boundary:
    This interpreter does not implement consciousness, memory writes,
    frequency causality, biological effects, or supernatural operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import datetime as _dt


REGISTRY_PATH = Path(__file__).with_name("anu28_registry.json")

NON_CLAIMS = {
    "frequency_causality": False,
    "consciousness_claim": False,
    "permanent_memory_claim": False,
    "supernatural_claim": False,
}

PRECEDENCE = {
    "prime": 1,
    "elemental": 2,
    "signal": 3,
}

DEFAULT_INSTRUCTIONS = {
    "Anu": "Establish the foundational context and core premise.",
    "Luma": "Expand scope and consider broader implications.",
    "Sethar": "Maintain cooperative synthesis and coherence.",
    "Nuru": "Track motion, evolution, and process flow.",
    "Keth": "Structure the response with clear logical balance.",
    "Vorin": "Treat the content as a directed signal or transmission.",
    "Reth": "Prioritize and emphasize the relevant concept.",
    "Uru": "Preserve continuity and connection across the packet.",
    "Mira": "Preserve memory, flow, and emotional continuity as context only.",
    "Jara": "Focus on transformation and actionable change.",
    "Ophi": "Use analytical abstraction and clear reasoning.",
    "Khel": "Ground the response in practical foundations.",
    "Eye": "Perform pattern recognition and perceptive analysis.",
    "Seraph": "Identify adaptive evolution and guidance pathways.",
    "Haru": "Mark emergence, genesis, or a new state.",
    "Thal": "Account for recursion, sequencing, and timefold dynamics.",
    "Rin": "Treat frequency-like details as symbolic modulation metadata only.",
    "Solun": "Clarify intent and illuminate coherence.",
    "Vesh": "Include contrast, uncertainty, and shadow-side analysis.",
    "Nial": "Synthesize parts into an integrated whole.",
    "Spike": "Increase emphasis or priority.",
    "Loop": "Iterate or examine recursive structure.",
    "Expand": "Expand the response with examples and wider context.",
    "Compress": "Compress the response and prioritize density.",
    "Packet": "Treat this as a discrete self-contained packet.",
    "Origin": "Identify and preserve the origin/source anchor.",
    "Broadcast": "Frame output for multi-node or public transmission.",
    "Sync": "Integrate multiple perspectives into a coherent output.",
}

DEFAULT_CONSTRAINTS = {
    "Sethar": {"tone": "cooperative"},
    "Ophi": {"mode": "analytical"},
    "Eye": {"mode": "pattern_analysis"},
    "Rin": {"frequency_causality": False},
    "Nial": {"requires_synthesis": True},
    "Reth": {"priority": "high"},
    "Spike": {"priority": "high"},
    "Loop": {"iteration": True},
    "Expand": {"response_format": "expanded"},
    "Compress": {"max_words": 300, "response_format": "concise"},
    "Sync": {"requires_synthesis": True},
}


@dataclass(frozen=True)
class GlyphRule:
    glyph: str
    code: str
    name: str
    ring: str
    meaning: str
    function: str
    frequency_hz: Optional[float] = None
    instruction: str = ""
    constraints: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConstraintMergeResult:
    constraints: Dict[str, Any]
    conflicts: List[Dict[str, Any]]


class ANU28RegistryError(RuntimeError):
    pass


class ANU28ValidationError(ValueError):
    pass


def load_registry(path: Path = REGISTRY_PATH) -> Dict[str, GlyphRule]:
    """Load glyph rules from anu28_registry.json.

    Falls back to ANU28RegistryError if the registry is missing or malformed.
    """
    if not path.exists():
        raise ANU28RegistryError(f"Registry file not found: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    rings = raw.get("rings")
    if not isinstance(rings, dict):
        raise ANU28RegistryError("Registry missing 'rings' object")

    rules: Dict[str, GlyphRule] = {}
    for ring_name, entries in rings.items():
        if not isinstance(entries, list):
            raise ANU28RegistryError(f"Registry ring '{ring_name}' must be a list")
        for item in entries:
            glyph = item["glyph"]
            name = item["name"]
            rules[glyph] = GlyphRule(
                glyph=glyph,
                code=item.get("code", ""),
                name=name,
                ring=ring_name,
                meaning=item.get("meaning", ""),
                function=item.get("function", ""),
                frequency_hz=item.get("frequency_hz"),
                instruction=DEFAULT_INSTRUCTIONS.get(name, item.get("function", "")),
                constraints=DEFAULT_CONSTRAINTS.get(name, {}),
            )
    return rules


def extract_glyphs(text: str, registry: Dict[str, GlyphRule]) -> Tuple[List[str], List[str]]:
    """Extract known and unknown non-whitespace glyph-like characters.

    Known glyphs are returned in-order. Unknown symbols are reported for audit.
    """
    known: List[str] = []
    unknown: List[str] = []
    for char in text:
        if char in registry:
            known.append(char)
        elif not char.isspace() and not char.isalnum() and char not in {"-", "_", ":", ".", ",", "'", '"', "[", "]", "{", "}", "(", ")", "/"}:
            unknown.append(char)
    return known, unknown


def merge_constraints(rules: List[GlyphRule]) -> ConstraintMergeResult:
    """Merge constraints with deterministic precedence and conflict reporting.

    Higher ring precedence wins when a key conflicts.
    Equal precedence keeps the later glyph's value and records a conflict.
    """
    constraints: Dict[str, Any] = {}
    source: Dict[str, GlyphRule] = {}
    conflicts: List[Dict[str, Any]] = []

    for rule in rules:
        for key, value in rule.constraints.items():
            if key not in constraints:
                constraints[key] = value
                source[key] = rule
                continue

            old_rule = source[key]
            old_value = constraints[key]
            if old_value == value:
                continue

            old_prec = PRECEDENCE.get(old_rule.ring, 0)
            new_prec = PRECEDENCE.get(rule.ring, 0)
            winner = rule if new_prec >= old_prec else old_rule
            winning_value = value if winner is rule else old_value

            conflicts.append({
                "constraint": key,
                "previous_glyph": old_rule.glyph,
                "previous_name": old_rule.name,
                "previous_value": old_value,
                "new_glyph": rule.glyph,
                "new_name": rule.name,
                "new_value": value,
                "resolution": f"{winner.glyph} {winner.name} wins by precedence/order",
            })

            constraints[key] = winning_value
            source[key] = winner

    return ConstraintMergeResult(constraints=constraints, conflicts=conflicts)


def compile_packet(glyph_text: str, intent: str, packet_id: str = "ANU28-COMPILED") -> Dict[str, Any]:
    """Compile glyph text and intent into a Universal Object style result."""
    registry = load_registry()
    glyphs, unknown = extract_glyphs(glyph_text, registry)

    if not glyphs:
        raise ANU28ValidationError("No known ANU-28 glyphs found in input")

    rules = [registry[g] for g in glyphs]
    ordered_rules = sorted(enumerate(rules), key=lambda pair: (PRECEDENCE.get(pair[1].ring, 0), pair[0]))
    sorted_rules = [rule for _, rule in ordered_rules]
    merge = merge_constraints(sorted_rules)

    instructions = [
        {
            "glyph": rule.glyph,
            "code": rule.code,
            "name": rule.name,
            "ring": rule.ring,
            "meaning": rule.meaning,
            "instruction": rule.instruction,
        }
        for rule in sorted_rules
    ]

    compiled_prompt = "\n".join([
        "SYSTEM INTENT:",
        *[f"- {i['glyph']} {i['name']}: {i['instruction']}" for i in instructions],
        "",
        "CONSTRAINTS:",
        json.dumps(merge.constraints, ensure_ascii=False, indent=2),
        "",
        "TASK:",
        intent,
        "",
        "BOUNDARY:",
        "Glyphs are semantic operators only. Symbolic frequency metadata is non-causal.",
    ])

    governance_state = "valid_with_warnings" if unknown or merge.conflicts else "valid"

    return {
        "object_type": "ANU28CompiledPromptObject",
        "version": "ANU-28-v1.1",
        "packet_id": packet_id,
        "timestamp_utc": _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "evidence_level": "E1_SYMBOLIC_SPECIFICATION",
        "governance_state": governance_state,
        "source_glyphs": glyphs,
        "unknown_glyphs": unknown,
        "instructions": instructions,
        "constraints": merge.constraints,
        "conflicts": merge.conflicts,
        "intent": intent,
        "compiled_prompt": compiled_prompt,
        "non_claims": NON_CLAIMS,
    }


if __name__ == "__main__":
    sample_glyphs = "◆ ● ✶ ◈ 𓂀 ∰ ⟴"
    sample_intent = "Analyze and integrate multiple viewpoints coherently."
    print(json.dumps(compile_packet(sample_glyphs, sample_intent), ensure_ascii=False, indent=2))
