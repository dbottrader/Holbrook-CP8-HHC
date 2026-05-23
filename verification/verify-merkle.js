/**
 * Merkle Tree Calculator with Inclusion Proofs
 * Computes Merkle root and generates inclusion proofs for any file.
 *
 * Usage:
 *   node verification/verify-merkle.js [--manifest sha256-manifest.json]
 *   node verification/verify-merkle.js proof <filepath>
 *
 * CP8 Protocol • ASIN-HHC Framework • Holbrook Distributed Lattice
 */

import { createHash } from 'crypto';
import { readFileSync, existsSync, writeFileSync } from 'fs';
import { resolve } from 'path';

function sha256Hex(data) {
  return createHash('sha256').update(data).digest('hex');
}

function sha256Str(data) {
  return createHash('sha256').update(data, 'utf-8').digest('hex');
}

function buildMerkleTree(leaves) {
  if (leaves.length === 0) return { root: sha256Str(''), tree: [[]] };
  let level = leaves.slice();
  if (level.length % 2 === 1) level.push(level[level.length - 1]);
  const tree = [level];
  while (level.length > 1) {
    const next = [];
    for (let i = 0; i < level.length; i += 2) {
      const left = level[i];
      const right = level[i + 1] || left;
      next.push(sha256Str(left + right));
    }
    level = next;
    tree.push(level);
  }
  return { root: tree[tree.length - 1][0], tree };
}

function getInclusionProof(tree, leafIndex) {
  const proof = [];
  let idx = leafIndex;
  for (let level = 0; level < tree.length - 1; level++) {
    const siblingIdx = idx % 2 === 0 ? idx + 1 : idx - 1;
    if (siblingIdx < tree[level].length) {
      proof.push({
        hash: tree[level][siblingIdx],
        direction: idx % 2 === 0 ? 'right' : 'left'
      });
    }
    idx = Math.floor(idx / 2);
  }
  return proof;
}

function verifyInclusionProof(leafHash, proof, expectedRoot) {
  let current = leafHash;
  for (const step of proof) {
    if (step.direction === 'right') {
      current = sha256Str(current + step.hash);
    } else {
      current = sha256Str(step.hash + current);
    }
  }
  return current === expectedRoot;
}

function main() {
  const args = process.argv.slice(2);
  const manifestPath = args[0] === '--manifest' ? args[1] : 'sha256-manifest.json';
  const command = args[0];

  if (!existsSync(manifestPath)) {
    console.error(`❌ Manifest not found: ${manifestPath}`);
    process.exit(2);
  }

  const data = JSON.parse(readFileSync(manifestPath, 'utf-8'));
  const metadata = data.metadata || {};
  const files = data.files || {};
  const entries = Object.entries(files);
  const leaves = entries.map(([_, info]) => info.sha256);
  const { root, tree } = buildMerkleTree(leaves);
  const storedRoot = metadata.merkle_root || '';

  console.log('='.repeat(60));
  console.log('  CP8 Merkle Tree Analysis');
  console.log('='.repeat(60));
  console.log(`  Files:      ${leaves.length}`);
  console.log(`  Tree depth: ${tree.length}`);
  console.log(`  Stored root:  ${storedRoot}`);
  console.log(`  Computed root: ${root}`);
  console.log(`  Match: ${root === storedRoot ? '✅ VALID' : '❌ MISMATCH'}`);
  console.log('='.repeat(60));

  // If proof command
  if (command === 'proof' && args[1]) {
    const targetPath = args[1];
    const idx = entries.findIndex(([p]) => p === targetPath);
    if (idx === -1) {
      console.error(`❌ File not found in manifest: ${targetPath}`);
      process.exit(1);
    }
    const proof = getInclusionProof(tree, idx);
    console.log(`\n  Inclusion proof for: ${targetPath}`);
    console.log(`  Leaf hash: ${leaves[idx]}`);
    console.log(`  Proof steps: ${proof.length}`);
    for (let i = 0; i < proof.length; i++) {
      const p = proof[i];
      console.log(`    [${i}] ${p.direction} sibling: ${p.hash.slice(0, 24)}...`);
    }
    const valid = verifyInclusionProof(leaves[idx], proof, root);
    console.log(`\n  Proof verification: ${valid ? '✅ VALID' : '❌ INVALID'}`);

    // Write proof to file
    const proofData = {
      file: targetPath,
      leaf_hash: leaves[idx],
      merkle_root: root,
      proof_steps: proof,
      verified: valid,
      protocol: 'ASH-0.2',
      timestamp: new Date().toISOString()
    };
    const proofPath = `verification/merkle-proof-${targetPath.replace(/[/\\]/g, '-')}.json`;
    writeFileSync(proofPath, JSON.stringify(proofData, null, 2));
    console.log(`  Proof saved: ${proofPath}`);
  }
}

main();
