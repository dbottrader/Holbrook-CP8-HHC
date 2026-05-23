# -*- coding: utf-8 -*-
"""
CP8 Deterministic Build Integrity Engine
Generates canonical SHA-256 manifest + Merkle root for Holbrook repo.

Usage:
    python3 scripts/build-merkle.py [--output-dir .] [--manifest manifest.json]

Output:
    - sha256-manifest.json   → file-level hashes
    - merkle-root.txt        → Merkle root hash
    - build-manifest.json    → full build metadata

CP8 Protocol • ASIN-HHC Framework • Holbrook Distributed Lattice
"""

import hashlib
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone


def sha256_file(filepath: Path) -> str:
    """Compute SHA-256 of file contents (binary-safe)."""
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def sha256_str(data: str) -> str:
    """Compute SHA-256 of a string (UTF-8)."""
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def get_tracked_files(repo_root: Path, exclude_patterns=None) -> list:
    """Get all tracked files in deterministic order."""
    if exclude_patterns is None:
        exclude_patterns = {
            '.git', '__pycache__', '.pyc', 'node_modules',
            '.DS_Store', 'Thumbs.db', '*.tmp', '*.log',
            'sha256-manifest.json', 'merkle-root.txt', 'build-manifest.json'
        }
    
    files = []
    for root, dirs, filenames in os.walk(repo_root):
        # Filter out excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_patterns and not d.startswith('.')]
        
        for fname in filenames:
            # Skip excluded patterns
            if any(fname.endswith(p.lstrip('*')) for p in exclude_patterns if p.startswith('*')):
                continue
            if fname in exclude_patterns:
                continue
            
            fpath = Path(root) / fname
            rel_path = fpath.relative_to(repo_root)
            files.append(rel_path)
    
    # Canonical deterministic ordering: alphabetical by relative path
    files.sort(key=lambda p: str(p).replace(os.sep, '/'))
    return files


def build_merkle_tree(hashes: list) -> list:
    """
    Build a Merkle tree from a list of leaf hashes.
    Returns list of lists, where each sublist is a tree level.
    """
    if not hashes:
        return []
    
    # Ensure even number of leaves by duplicating last if odd
    leaves = hashes[:]
    if len(leaves) % 2 == 1:
        leaves.append(leaves[-1])
    
    tree = [leaves]
    
    while len(tree[-1]) > 1:
        current_level = tree[-1]
        next_level = []
        
        for i in range(0, len(current_level), 2):
            left = current_level[i]
            right = current_level[i + 1] if i + 1 < len(current_level) else left
            # Concatenate hex strings, hash the concatenation
            combined = left + right
            parent = sha256_str(combined)
            next_level.append(parent)
        
        tree.append(next_level)
    
    return tree


def main():
    import argparse
    parser = argparse.ArgumentParser(description='CP8 Deterministic Build Engine')
    parser.add_argument('--output-dir', default='.', help='Output directory for manifests')
    parser.add_argument('--repo-root', default='.', help='Repository root path')
    parser.add_argument('--manifest-name', default='sha256-manifest.json', help='Manifest filename')
    parser.add_argument('--build-name', default=None, help='Build name override')
    args = parser.parse_args()
    
    repo_root = Path(args.repo_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get tracked files
    files = get_tracked_files(repo_root)
    
    # Compute file hashes
    file_manifest = {}
    leaf_hashes = []
    
    for rel_path in files:
        abs_path = repo_root / rel_path
        file_hash = sha256_file(abs_path)
        file_manifest[str(rel_path).replace(os.sep, '/')] = {
            'sha256': file_hash,
            'size': abs_path.stat().st_size
        }
        leaf_hashes.append(file_hash)
    
    # Build Merkle tree
    tree = build_merkle_tree(leaf_hashes)
    merkle_root = tree[-1][0] if tree else sha256_str('')
    
    # Compute combined signature
    canonical_manifest = json.dumps(file_manifest, sort_keys=True, separators=(',', ':'))
    combined_signature = sha256_str(canonical_manifest + merkle_root)
    
    # Build metadata
    build_name = args.build_name or f"Holbrook-CP8-HHC-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    
    build_metadata = {
        'build_name': build_name,
        'repo': 'Holbrook-CP8-HHC',
        'protocol': 'ASH-0.2',
        'hos_ground_truth': '63b5160ef51f0464295e86888c3e6605d8f6cc970635183887083818e8749320',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'total_files': len(files),
        'total_bytes': sum(f['size'] for f in file_manifest.values()),
        'merkle_root': merkle_root,
        'combined_signature': combined_signature,
        'build_tool': 'build-merkle.py',
        'version': '1.0.0'
    }
    
    # Write outputs
    manifest_path = output_dir / args.manifest_name
    with open(manifest_path, 'w') as f:
        json.dump({
            'metadata': build_metadata,
            'files': file_manifest
        }, f, indent=2)
    
    merkle_path = output_dir / 'merkle-root.txt'
    with open(merkle_path, 'w') as f:
        f.write(f"{merkle_root}\n")
    
    build_manifest_path = output_dir / 'build-manifest.json'
    with open(build_manifest_path, 'w') as f:
        json.dump(build_metadata, f, indent=2)
    
    # Print summary
    print(f"{'='*60}")
    print(f"  CP8 Deterministic Build Complete")
    print(f"{'='*60}")
    print(f"  Build:    {build_name}")
    print(f"  Files:    {len(files)}")
    print(f"  Bytes:    {build_metadata['total_bytes']:,}")
    print(f"  Merkle:   {merkle_root}")
    print(f"  Combined: {combined_signature}")
    print(f"{'='*60}")
    print(f"  Manifest: {manifest_path}")
    print(f"  Merkle:   {merkle_path}")
    print(f"  Build:    {build_manifest_path}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
