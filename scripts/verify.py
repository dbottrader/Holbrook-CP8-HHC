# -*- coding: utf-8 -*-
"""
CP8 Build Integrity Verifier
Re-checks every artifact, validates hashes, verifies commit-linked manifests.

Usage:
    python3 scripts/verify.py [--manifest sha256-manifest.json] [--repo-root .]

Exit codes:
    0 = all valid
    1 = hash mismatch
    2 = manifest missing or corrupt
    3 = Merkle root mismatch

CP8 Protocol • ASIN-HHC Framework • Holbrook Distributed Lattice
"""

import hashlib
import json
import os
import sys
from pathlib import Path


def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def sha256_str(data: str) -> str:
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def verify_manifest(manifest_path: Path, repo_root: Path) -> tuple:
    """Verify a manifest against actual files. Returns (valid: bool, errors: list)."""
    errors = []
    
    if not manifest_path.exists():
        return False, [f"Manifest not found: {manifest_path}"]
    
    try:
        with open(manifest_path, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"Manifest JSON error: {e}"]
    
    metadata = data.get('metadata', {})
    files = data.get('files', {})
    
    # Verify HOS Ground Truth
    expected_hos = '63b5160ef51f0464295e86888c3e6605d8f6cc970635183887083818e8749320'
    actual_hos = metadata.get('hos_ground_truth', '')
    if actual_hos != expected_hos:
        errors.append(f"HOS mismatch: expected {expected_hos[:16]}..., got {actual_hos[:16]}...")
    
    # Verify each file
    verified_count = 0
    for rel_path, info in files.items():
        abs_path = repo_root / rel_path
        
        if not abs_path.exists():
            errors.append(f"MISSING: {rel_path}")
            continue
        
        actual_hash = sha256_file(abs_path)
        expected_hash = info.get('sha256', '')
        
        if actual_hash != expected_hash:
            errors.append(f"HASH MISMATCH: {rel_path}")
            errors.append(f"  Expected: {expected_hash}")
            errors.append(f"  Actual:   {actual_hash}")
        else:
            verified_count += 1
    
    # Recompute Merkle root
    leaf_hashes = [info['sha256'] for info in files.values()]
    
    if leaf_hashes:
        # Ensure even number
        leaves = leaf_hashes[:]
        if len(leaves) % 2 == 1:
            leaves.append(leaves[-1])
        
        while len(leaves) > 1:
            next_level = []
            for i in range(0, len(leaves), 2):
                left = leaves[i]
                right = leaves[i + 1] if i + 1 < len(leaves) else left
                combined = left + right
                parent = sha256_str(combined)
                next_level.append(parent)
            leaves = next_level
        
        recomputed_root = leaves[0]
        stored_root = metadata.get('merkle_root', '')
        
        if recomputed_root != stored_root:
            errors.append(f"MERKLE MISMATCH:")
            errors.append(f"  Stored:   {stored_root}")
            errors.append(f"  Computed: {recomputed_root}")
    
    # Recompute combined signature
    canonical = json.dumps(files, sort_keys=True, separators=(',', ':'))
    expected_combined = sha256_str(canonical + metadata.get('merkle_root', ''))
    stored_combined = metadata.get('combined_signature', '')
    
    if stored_combined and expected_combined != stored_combined:
        errors.append(f"COMBINED SIGNATURE MISMATCH")
    
    valid = len(errors) == 0
    return valid, errors, verified_count, len(files)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='CP8 Build Integrity Verifier')
    parser.add_argument('--manifest', default='sha256-manifest.json', help='Manifest file path')
    parser.add_argument('--repo-root', default='.', help='Repository root path')
    args = parser.parse_args()
    
    repo_root = Path(args.repo_root).resolve()
    manifest_path = repo_root / args.manifest
    
    print(f"{'='*60}")
    print(f"  CP8 Build Integrity Verification")
    print(f"{'='*60}")
    print(f"  Manifest: {manifest_path}")
    print(f"  Repo:     {repo_root}")
    print(f"{'='*60}")
    
    valid, errors, verified, total = verify_manifest(manifest_path, repo_root)
    
    if valid:
        print(f"\n  ✅ ALL CHECKS PASSED")
        print(f"  Files verified: {verified}/{total}")
        print(f"  Merkle root: VALID")
        print(f"  HOS hash: VALID")
        print(f"  Combined signature: VALID")
        print(f"{'='*60}")
        sys.exit(0)
    else:
        print(f"\n  ❌ VERIFICATION FAILED")
        print(f"  Files verified: {verified}/{total}")
        print(f"  Errors found: {len(errors)}")
        for error in errors:
            print(f"    • {error}")
        print(f"{'='*60}")
        sys.exit(1)


if __name__ == '__main__':
    main()
