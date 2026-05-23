/**
 * SHA-256 Inventory Generator
 * Scans the repository and produces a canonical file manifest.
 *
 * Usage:
 *   node verification/generate-inventory.js [--output-dir .]
 *
 * Output:
 *   - sha256-manifest.json   → file-level hashes
 *   - merkle-root.txt        → Merkle root hash
 *   - build-manifest.json    → full build metadata
 *
 * CP8 Protocol • ASIN-HHC Framework • Holbrook Distributed Lattice
 */

import { createHash } from 'crypto';
import { readdirSync, statSync, readFileSync, writeFileSync } from 'fs';
import { resolve, relative, join } from 'path';

const EXCLUDE = new Set([
  '.git', '__pycache__', 'node_modules', '.DS_Store',
  'Thumbs.db', '.pyc', '.tmp', '.log',
  'sha256-manifest.json', 'merkle-root.txt', 'build-manifest.json'
]);

const EXCLUDE_PATTERNS = [
  /^\./, /^__pycache__/, /node_modules/, /\.pyc$/, /\.tmp$/, /\.log$/
];

function canonicalJsonStringify(obj) {
  const keys = Object.keys(obj).sort();
  const parts = keys.map(k => {
    const val = obj[k];
    if (typeof val === 'object' && val !== null) {
      const innerKeys = Object.keys(val).sort();
      const innerParts = innerKeys.map(ik => {
        const innerVal = val[ik];
        if (typeof innerVal === 'string') {
          return `"${ik}":"${innerVal}"`;
        } else {
          return `"${ik}":${innerVal}`;
        }
      });
      return `"${k}":{${innerParts.join(',')}}`;
    }
    return `"${k}":"${val}"`;
  });
  return `{${parts.join(',')}}`;
}

function sha256File(path) {
  const data = readFileSync(path);
  return createHash('sha256').update(data).digest('hex');
}

function sha256Str(data) {
  return createHash('sha256').update(data, 'utf-8').digest('hex');
}

function getTrackedFiles(dir, base = dir) {
  const files = [];
  function walk(current) {
    const entries = readdirSync(current, { withFileTypes: true });
    for (const entry of entries) {
      if (EXCLUDE.has(entry.name)) continue;
      if (EXCLUDE_PATTERNS.some(p => p.test(entry.name))) continue;
      const full = join(current, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else {
        files.push(relative(base, full).replace(/\\/g, '/'));
      }
    }
  }
  walk(dir);
  return files.sort();
}

function buildMerkleTree(hashes) {
  if (hashes.length === 0) return [[]];
  let level = hashes.slice();
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
  return tree;
}

function main() {
  const args = {};
  for (let i = 2; i < process.argv.length; i += 2) {
    const key = process.argv[i].replace(/^--/, '');
    args[key] = process.argv[i + 1];
  }

  const repoRoot = resolve(args['repo-root'] || '.');
  const outputDir = resolve(args['output-dir'] || '.');
  const buildName = args['build-name'] || `Holbrook-CP8-HHC-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}`;

  const files = getTrackedFiles(repoRoot, repoRoot);
  const fileManifest = {};
  const leafHashes = [];
  let totalBytes = 0;

  for (const relPath of files) {
    const absPath = resolve(repoRoot, relPath);
    const fileHash = sha256File(absPath);
    const size = statSync(absPath).size;
    fileManifest[relPath] = { sha256: fileHash, size };
    leafHashes.push(fileHash);
    totalBytes += size;
  }

  const tree = buildMerkleTree(leafHashes);
  const merkleRoot = tree[tree.length - 1][0] || sha256Str('');

  const canonical = canonicalJsonStringify(fileManifest);
  const combinedSignature = sha256Str(canonical + merkleRoot);

  const buildMetadata = {
    build_name: buildName,
    repo: 'Holbrook-CP8-HHC',
    protocol: 'ASH-0.2',
    hos_ground_truth: '63b5160ef51f0464295e86888c3e6605d8f6cc970635183887083818e8749320',
    timestamp: new Date().toISOString(),
    total_files: files.length,
    total_bytes: totalBytes,
    merkle_root: merkleRoot,
    combined_signature: combinedSignature,
    build_tool: 'generate-inventory.js',
    version: '0.4.0'
  };

  writeFileSync(join(outputDir, 'sha256-manifest.json'),
    JSON.stringify({ metadata: buildMetadata, files: fileManifest }, null, 2));
  writeFileSync(join(outputDir, 'merkle-root.txt'), merkleRoot + '\n');
  writeFileSync(join(outputDir, 'build-manifest.json'),
    JSON.stringify(buildMetadata, null, 2));

  console.log('='.repeat(60));
  console.log('  CP8 Deterministic Build Complete');
  console.log('='.repeat(60));
  console.log(`  Build:    ${buildName}`);
  console.log(`  Files:    ${files.length}`);
  console.log(`  Bytes:    ${totalBytes.toLocaleString()}`);
  console.log(`  Merkle:   ${merkleRoot}`);
  console.log(`  Combined: ${combinedSignature}`);
  console.log('='.repeat(60));
  console.log(`  Manifest: ${join(outputDir, 'sha256-manifest.json')}`);
  console.log(`  Merkle:   ${join(outputDir, 'merkle-root.txt')}`);
  console.log(`  Build:    ${join(outputDir, 'build-manifest.json')}`);
  console.log('='.repeat(60));
}

main();
