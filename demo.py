#!/usr/bin/env python3
"""
Holbrook 30-Second Packet Demo

Run a complete provenance workflow in one command:
1. Build a manifest + Merkle root.
2. Create an audit packet.
3. Simulate a second agent attesting the packet.
4. Verify the chain.

Usage:
    python3 demo.py

No dependencies beyond Python 3.10+.
"""

import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_str(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def hash_canonical(obj: dict) -> str:
    return sha256_str(json.dumps(obj, sort_keys=True, separators=(",", ":")))


class PacketDemo:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.file = workspace / "demo-output.txt"
        self.packets: list[dict] = []

    def run(self) -> bool:
        print("=" * 60)
        print("  Holbrook 30-Second Provenance Demo")
        print("=" * 60)

        # 1. Simulate an agent producing a file.
        print("\n[1/5] Agent 'builder' writes a file...")
        self.file.write_text(
            f"Automated build artifact generated at {timestamp()}\n"
        )
        print(f"      {self.file.name}")

        # 2. Build a manifest + Merkle root for the workspace.
        print("\n[2/5] Building hash manifest and Merkle root...")
        files = sorted([p for p in self.workspace.iterdir() if p.is_file()])
        manifest = {}
        leaf_hashes = []
        for f in files:
            rel = f.name
            manifest[rel] = {"sha256": sha256_file(f), "size": f.stat().st_size}
            leaf_hashes.append(manifest[rel]["sha256"])

        merkle_root = self._merkle_root(leaf_hashes)
        print(f"      files:      {len(files)}")
        print(f"      merkle_root: {merkle_root}")

        # 3. Create an audit packet for this action.
        print("\n[3/5] Creating audit packet...")
        packet = self._create_packet(
            agent_id="builder-1",
            agent_name="Builder Agent",
            model="demo-llm",
            action_type="create",
            target=str(self.file),
            description="Generated demo artifact",
            extra={"manifest": manifest, "merkle_root": merkle_root},
        )
        print(f"      packet_id:  {packet['packet_id']}")
        print(f"      sha256:     {packet['provenance']['sha256']}")

        # 4. Simulate a second agent attesting the packet.
        print("\n[4/5] Agent 'reviewer' attests the packet...")
        attestation = {
            "agent_id": "reviewer-1",
            "agent_name": "Reviewer Agent",
            "model": "demo-llm",
            "signature": sha256_str(
                packet["provenance"]["sha256"] + "|reviewer-1|approved"
            ),
            "timestamp": timestamp(),
            "verdict": "approved",
        }
        packet["provenance"]["attestations"].append(attestation)
        # Re-hash after attestation to keep packet self-consistent.
        packet["provenance"]["sha256"] = hash_canonical(
            {k: v for k, v in packet.items() if k != "provenance"}
        )
        self.packets[-1] = packet
        print(f"      attested by: reviewer-1 ({attestation['verdict']})")

        # 5. Verify the chain.
        print("\n[5/5] Verifying chain...")
        valid, errors = self._verify_chain()
        if valid:
            print("      ✅ chain valid")
            print("      ✅ packet hash valid")
            print("      ✅ attestation present")
        else:
            print("      ❌ verification failed")
            for e in errors:
                print(f"         - {e}")

        # Persist demo artifacts.
        data_dir = Path("demo-artifacts")
        data_dir.mkdir(exist_ok=True)
        (data_dir / "packets.jsonl").write_text(
            "\n".join(json.dumps(p, separators=(",", ":")) for p in self.packets) + "\n"
        )

        print("\n" + "=" * 60)
        print("  Demo artifacts written to ./demo-artifacts/")
        print("=" * 60)
        return valid

    def _merkle_root(self, leaves: list[str]) -> str:
        if not leaves:
            return sha256_str("")
        level = leaves[:]
        if len(level) % 2 == 1:
            level.append(level[-1])
        while len(level) > 1:
            next_level = []
            for i in range(0, len(level), 2):
                combined = level[i] + level[i + 1]
                next_level.append(sha256_str(combined))
            level = next_level
            if len(level) > 1 and len(level) % 2 == 1:
                level.append(level[-1])
        return level[0]

    def _create_packet(
        self,
        agent_id: str,
        agent_name: str,
        model: str,
        action_type: str,
        target: str,
        description: str,
        extra: dict | None = None,
    ) -> dict:
        packet = {
            "schema_version": "CP8-0.1",
            "packet_type": "audit",
            "packet_id": f"pkt-{len(self.packets) + 1:04d}",
            "timestamp": timestamp(),
            "agent": {"id": agent_id, "name": agent_name, "model": model},
            "action": {
                "type": action_type,
                "target": target,
                "description": description,
            },
            "metadata": {
                "demo": True,
                **(extra or {}),
            },
            "provenance": {
                "sha256": "",
                "previous_packet_id": None,
                "previous_sha256": None,
                "attestations": [],
            },
        }
        if self.packets:
            prev = self.packets[-1]
            packet["provenance"]["previous_packet_id"] = prev["packet_id"]
            packet["provenance"]["previous_sha256"] = prev["provenance"]["sha256"]
        packet["provenance"]["sha256"] = hash_canonical(
            {k: v for k, v in packet.items() if k != "provenance"}
        )
        self.packets.append(packet)
        return packet

    def _verify_chain(self) -> tuple[bool, list[str]]:
        errors = []
        for i, packet in enumerate(self.packets):
            expected = hash_canonical(
                {k: v for k, v in packet.items() if k != "provenance"}
            )
            if packet["provenance"]["sha256"] != expected:
                errors.append(f"packet {i}: hash mismatch")
            if i > 0:
                prev = self.packets[i - 1]
                if packet["provenance"]["previous_packet_id"] != prev["packet_id"]:
                    errors.append(f"packet {i}: previous_packet_id mismatch")
                if (
                    packet["provenance"]["previous_sha256"]
                    != prev["provenance"]["sha256"]
                ):
                    errors.append(f"packet {i}: previous_sha256 mismatch")
        # Check that final packet has at least one attestation in this demo.
        if self.packets and not self.packets[-1]["provenance"]["attestations"]:
            errors.append("last packet: missing attestation")
        return len(errors) == 0, errors


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="holbrook-demo-") as tmp:
        workspace = Path(tmp)
        ok = PacketDemo(workspace).run()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
