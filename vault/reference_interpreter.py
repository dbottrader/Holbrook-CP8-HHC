"""
ANU-28 Reference Interpreter v1.0

Grounded reference implementation for parsing glyph packets into deterministic
plain-language prompt instructions.

This file treats glyphs as semantic operators only. It makes no claims of
frequency causality, consciousness, permanent memory, or supernatural effects.
"""

from dataclasses import dataclass
from typing import Dict, List, Any


@dataclass(frozen=True)
class GlyphRule:
    glyph: str
    name: str
    ring: str
    instruction: str
    constraints: Dict[str, Any]


GLYPHS: Dict[str, GlyphRule] = {
    "✶": GlyphRule("✶", "Anu", "prime", "Establish the foundational context and core premise.", {}),
    "◎": GlyphRule("◎", "Luma", "prime", "Expand scope and consider broader implications.", {}),
    "◈": GlyphRule("◈", "Sethar", "prime", "Maintain cooperative synthesis and coherence.", {"tone": "cooperative"}),
    "ꗃ": GlyphRule("ꗃ", "Nuru", "prime", "Track motion, evolution, and process flow.", {}),
    "✦": GlyphRule("✦", "Keth", "prime", "Structure the response with clear logical balance.", {}),
    "ᚾ": GlyphRule("ᚾ", "Vorin", "prime", "Treat the content as a directed signal or transmission.", {}),
    "Ϟ": GlyphRule("Ϟ", "Reth", "prime", "Prioritize and emphasize the relevant concept.", {"priority": "high"}),
    "⚯": GlyphRule("⚯", "Uru", "prime", "Preserve continuity and connection across the packet.", {}),

    "ᛗ": GlyphRule("ᛗ", "Mira", "elemental", "Preserve memory, flow, and emotional continuity.", {}),
    "ᛃ": GlyphRule("ᛃ", "Jara", "elemental", "Focus on transformation and actionable change.", {}),
    "ϴ": GlyphRule("ϴ", "Ophi", "elemental", "Use analytical abstraction and clear reasoning.", {"mode": "analytical"}),
    "ᚲ": GlyphRule("ᚲ", "Khel", "elemental", "Ground the response in practical foundations.", {}),
    "𓂀": GlyphRule("𓂀", "Eye", "elemental", "Perform pattern recognition and perceptive analysis.", {"mode": "pattern_analysis"}),
    "𓆣": GlyphRule("𓆣", "Seraph", "elemental", "Identify adaptive evolution and guidance pathways.", {}),
    "𐃘": GlyphRule("𐃘", "Haru", "elemental", "Mark emergence, genesis, or a new state.", {}),
    "𐡷": GlyphRule("𐡷", "Thal", "elemental", "Account for recursion, sequencing, and timefold dynamics.", {}),
    "𖤓": GlyphRule("𖤓", "Rin", "elemental", "Treat frequency-like details as symbolic modulation metadata.", {"frequency_causality": False}),
    "𖤐": GlyphRule("𖤐", "Solun", "elemental", "Clarify intent and illuminate coherence.", {}),
    "𖣘": GlyphRule("𖣘", "Vesh", "elemental", "Include contrast, uncertainty, and shadow-side analysis.", {}),
    "𖣔": GlyphRule("𖣔", "Nial", "elemental", "Synthesize parts into an integrated whole.", {"requires_synthesis": True}),

    "↯": GlyphRule("↯", "Spike", "signal", "Increase emphasis or priority.", {"priority": "high"}),
    "⟲": GlyphRule("⟲", "Loop", "signal", "Iterate or examine recursive structure.", {"iteration": True}),
    "⇱": GlyphRule("⇱", "Expand", "signal", "Expand the response with examples and wider context.", {"response_format": "expanded"}),
    "⟴": GlyphRule("⟴", "Compress", "signal", "Compress the response and prioritize density.", {"max_words": 300, "response_format": "concise"}),
    "◆": GlyphRule("◆", "Packet", "signal", "Treat this as a discrete self-contained packet.", {}),
    "●": GlyphRule("●", "Origin", "signal", "Identify and preserve the origin/source anchor.", {}),
    "✇": GlyphRule("✇", "Broadcast", "signal", "Frame output for multi-node or public transmission.", {}),
    "∰": GlyphRule("∰", "Sync", "signal", "Integrate multiple perspectives into a coherent output.", {"requires_synthesis": True}),
}


PRECEDENCE = {"prime": 1, "elemental": 2, "signal": 3}


def extract_glyphs(text: str) -> List[str]:
    return [char for char in text if char in GLYPHS]


def compile_packet(glyphs: List[str], intent: str) -> Dict[str, Any]:
    rules = [GLYPHS[g] for g in glyphs if g in GLYPHS]
    rules = sorted(rules, key=lambda r: PRECEDENCE[r.ring])

    constraints: Dict[str, Any] = {}
    instructions: List[str] = []

    for rule in rules:
        instructions.append(f"{rule.glyph} {rule.name}: {rule.instruction}")
        constraints.update(rule.constraints)

    system_intent = {
        "instructions": instructions,
        "constraints": constraints,
        "task": intent,
        "boundary": "Glyphs are semantic operators only; symbolic metadata is non-causal."
    }
    return system_intent


if __name__ == "__main__":
    sample = "◆ ● ✶ ◈ 𓂀 ∰"
    intent = "Analyze and integrate multiple viewpoints coherently."
    print(compile_packet(extract_glyphs(sample), intent))
