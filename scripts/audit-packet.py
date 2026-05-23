#!/usr/bin/env python3
"""
CP8 Audit Packet Engine
Generates, verifies, and chains CP8 audit packets.
CP8 Protocol • ASIN-HHC Framework • Holbrook Distributed Lattice
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

HOS_GROUND_TRUTH = "63b5160ef51f0464295e86888c3e6605d8f6cc970635183887083818e8749320"
PACKET_LOG = Path(__file__).parent.parent / "audit-packets.jsonl"

class AuditEngine:
    def __init__(self, agent_id, agent_name, model):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.model = model
        self.packets = []
        self._load_existing()
    
    def _load_existing(self):
        if PACKET_LOG.exists():
            with open(PACKET_LOG, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.packets.append(json.loads(line))
    
    def create_packet(self, action_type, target, description, attestations=None):
        packet_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        packet = {
            "schema_version": "CP8-0.1",
            "packet_type": "audit",
            "packet_id": packet_id,
            "timestamp": timestamp,
            "agent": {"id": self.agent_id, "name": self.agent_name, "model": self.model},
            "action": {"type": action_type, "target": target, "description": description},
            "provenance": {
                "sha256": "",
                "previous_packet_id": None,
                "previous_sha256": None,
                "attestations": attestations or []
            },
            "metadata": {
                "harmonyos_mapped": True,
                "hhc_enabled": True,
                "agents": ["grok", "kimi"],
                "hos_ground_truth": HOS_GROUND_TRUTH
            }
        }
        if self.packets:
            prev = self.packets[-1]
            packet["provenance"]["previous_packet_id"] = prev["packet_id"]
            packet["provenance"]["previous_sha256"] = prev["provenance"]["sha256"]
        import hashlib
        packet_copy = {k: v for k, v in packet.items() if k != "provenance"}
        canonical = json.dumps(packet_copy, sort_keys=True, separators=(',', ':'))
        packet["provenance"]["sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
        self.packets.append(packet)
        self._save_packet(packet)
        return packet
    
    def _save_packet(self, packet):
        with open(PACKET_LOG, 'a') as f:
            f.write(json.dumps(packet, separators=(',', ':')) + '\n')
    
    def verify(self):
        errors = []
        for i, packet in enumerate(self.packets):
            import hashlib
            packet_copy = {k: v for k, v in packet.items() if k != "provenance"}
            canonical = json.dumps(packet_copy, sort_keys=True, separators=(',', ':'))
            computed = hashlib.sha256(canonical.encode()).hexdigest()
            stored = packet.get("provenance", {}).get("sha256", "")
            if computed != stored:
                errors.append(f"Packet {i}: hash mismatch")
            if i > 0:
                prev = self.packets[i-1]
                if packet.get("provenance", {}).get("previous_packet_id") != prev.get("packet_id"):
                    errors.append(f"Packet {i}: previous_packet_id mismatch")
                if packet.get("provenance", {}).get("previous_sha256") != prev.get("provenance", {}).get("sha256"):
                    errors.append(f"Packet {i}: previous_sha256 mismatch")
        return len(errors) == 0, errors
    
    def stats(self):
        valid, errors = self.verify()
        return {
            "total_packets": len(self.packets),
            "chain_valid": valid,
            "errors": errors,
            "last_packet": self.packets[-1]["packet_id"] if self.packets else None,
            "last_timestamp": self.packets[-1]["timestamp"] if self.packets else None
        }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CP8 Audit Engine")
    parser.add_argument("--agent-id", default="holbrook-engine")
    parser.add_argument("--agent-name", default="Holbrook Engine")
    parser.add_argument("--model", default="system")
    parser.add_argument("action", choices=["create", "verify", "stats"])
    parser.add_argument("--type", help="Action type for create")
    parser.add_argument("--target", help="Target for create")
    parser.add_argument("--description", help="Description for create")
    args = parser.parse_args()
    engine = AuditEngine(args.agent_id, args.agent_name, args.model)
    if args.action == "create":
        packet = engine.create_packet(args.type, args.target, args.description)
        print(json.dumps(packet, indent=2))
    elif args.action == "verify":
        valid, errors = engine.verify()
        print(f"Chain valid: {valid}")
        if errors:
            for e in errors:
                print(f"  ERROR: {e}")
    elif args.action == "stats":
        print(json.dumps(engine.stats(), indent=2))
