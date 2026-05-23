/**
 * SHA-256 Verification Suite
 * Re-checks every artifact against the canonical manifest.
 *
 * Usage:
 *   node verification/verify-all.js [--manifest sha256-manifest.json]
 *
 * Exit codes:
 *   0 = all valid
 *   1 = hash mismatch
 *   2 = manifest missing or corrupt
 *   3 = Merkle root mismatch
 *
 * CP8 Protocol • ASIN-HHC Framework • Holbrook Distributed Lattice
 */

import { createHash } from 'crypto';
import { readFileSync, existsSync } from 'fs';
import { resolve } from 'path';

const HOS_GROUND_TRUTH = '63b5160ef51f0464295e86888c3e6605d8f6cc970635183887083818e8749320';

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

function buildMerkleRoot(hashes) {
  if (hashes.length === 0) return sha256Str('');
  let level = hashes.slice();
  if (level.length % 2 === 1) level.push(level[level.length - 1]);
  while (level.length > 1) {
    const next = [];
    for (let i = 0; i < level.length; i += 2) {
      const left = level[i];
      const right = level[i + 1] || left;
      next.push(sha256Str(left + right));
    }
    level = next;
  }
  return level[0];
}

function verify(args) {
  const manifestPath = args.manifest || 'sha256-manifest.json';
  const repoRoot = resolve(args.repoRoot || '.');

  console.log('='.repeat(60));
  console.log('  CP8 Build Integrity Verification (Node.js)');
  console.log('='.repeat(60));
  console.log(`  Manifest: ${manifestPath}`);
  console.log(`  Repo:     ${repoRoot}`);
  console.log('='.repeat(60));

  if (!existsSync(manifestPath)) {
    console.error('\n  ❌ Manifest not found');
    process.exit(2);
  }

  let data;
  try {
    data = JSON.parse(readFileSync(manifestPath, 'utf-8'));
  } catch (e) {
    console.error(`\n  ❌ Manifest JSON error: ${e.message}`);
    process.exit(2);
  }

  const metadata = data.metadata || {};
  const files = data.files || {};
  const errors = [];
  let verified = 0;

  // HOS Ground Truth check
  const actualHos = metadata.hos_ground_truth || '';
  if (actualHos !== HOS_GROUND_TRUTH) {
    errors.push(`HOS mismatch: expected ${HOS_GROUND_TRUTH.slice(0, 16)}..., got ${actualHos.slice(0, 16)}...`);
  }

  // File-level verification
  for (const [relPath, info] of Object.entries(files)) {
    const absPath = resolve(repoRoot, relPath);
    if (!existsSync(absPath)) {
      errors.push(`MISSING: ${relPath}`);
      continue;
    }
    const actualHash = sha256File(absPath);
    const expectedHash = info.sha256;
    if (actualHash !== expectedHash) {
      errors.push(`HASH MISMATCH: ${relPath}`);
      errors.push(`  Expected: ${expectedHash}`);
      errors.push(`  Actual:   ${actualHash}`);
    } else {
      verified++;
    }
  }

  // Merkle root verification
  const leafHashes = Object.values(files).map(f => f.sha256);
  const recomputedRoot = buildMerkleRoot(leafHashes);
  const storedRoot = metadata.merkle_root || '';
  if (recomputedRoot !== storedRoot) {
    errors.push(`MERKLE MISMATCH: stored=${storedRoot}, computed=${recomputedRoot}`);
  }

  // Combined signature verification
  const canonical = canonicalJsonStringify(files);
  const expectedCombined = sha256Str(canonical + storedRoot);
  const storedCombined = metadata.combined_signature || '';
  if (storedCombined && expectedCombined !== storedCombined) {
    errors.push('COMBINED SIGNATURE MISMATCH');
    errors.push(`  Expected: ${expectedCombined}`);
    errors.push(`  Stored:   ${storedCombined}`);
  }

  const total = Object.keys(files).length;

  if (errors.length === 0) {
    console.log('\n  ✅ ALL CHECKS PASSED');
    console.log(`  Files verified: ${verified}/${total}`);
    console.log(`  Merkle root: VALID`);
    console.log(`  HOS hash: VALID`);
    console.log(`  Combined signature: VALID`);
    console.log('='.repeat(60));
    process.exit(0);
  } else {
    console.log('\n  ❌ VERIFICATION FAILED');
    console.log(`  Files verified: ${verified}/${total}`);
    console.log(`  Errors found: ${errors.length}`);
    for (const err of errors) {
      console.log(`    • ${err}`);
    }
    console.log('='.repeat(60));
    process.exit(1);
  }
}

// CLI
const args = {};
for (let i = 2; i < process.argv.length; i += 2) {
  const key = process.argv[i].replace(/^--/, '');
  args[key] = process.argv[i + 1];
}
verify(args);
