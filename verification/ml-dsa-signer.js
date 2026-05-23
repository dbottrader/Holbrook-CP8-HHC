/**
 * ML-DSA Signer (FIPS 204)
 * Quantum-resistant digital signature using @noble/post-quantum
 *
 * Usage:
 *   npm install @noble/post-quantum
 *   node verification/ml-dsa-signer.js sign <message>
 *   node verification/ml-dsa-signer.js verify <message> <sig> <pubkey>
 *   node verification/ml-dsa-signer.js keygen
 *
 * CP8 Protocol • ASIN-HHC Framework • Holbrook Distributed Lattice
 */

import { ml_dsa65 } from '@noble/post-quantum/ml-dsa';
import { randomBytes } from 'crypto';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { createHash } from 'crypto';

const KEY_FILE = 'verification/ml-dsa-key.json';

function sha256Hex(data) {
  return createHash('sha256').update(data).digest('hex');
}

function generateKeypair() {
  const seed = randomBytes(32);
  const keys = ml_dsa65.keygen(seed);
  const keyData = {
    protocol: 'ASH-0.2',
    algorithm: 'ML-DSA-65',
    standard: 'FIPS-204',
    seed: seed.toString('base64'),
    public_key: Buffer.from(keys.public_key).toString('base64'),
    secret_key: Buffer.from(keys.secret_key).toString('base64'),
    fingerprint: sha256Hex(keys.public_key).slice(0, 16),
    created: new Date().toISOString()
  };
  writeFileSync(KEY_FILE, JSON.stringify(keyData, null, 2));
  console.log(`🔐 ML-DSA-65 keypair generated`);
  console.log(`   Fingerprint: ${keyData.fingerprint}`);
  console.log(`   Stored: ${KEY_FILE}`);
  return keys;
}

function loadKeypair() {
  if (!existsSync(KEY_FILE)) {
    console.error('❌ No keyfile found. Run: node verification/ml-dsa-signer.js keygen');
    process.exit(1);
  }
  const data = JSON.parse(readFileSync(KEY_FILE, 'utf-8'));
  return {
    public_key: Buffer.from(data.public_key, 'base64'),
    secret_key: Buffer.from(data.secret_key, 'base64')
  };
}

function sign(message) {
  const keys = loadKeypair();
  const msgBytes = Buffer.from(message, 'utf-8');
  const sig = ml_dsa65.sign(keys.secret_key, msgBytes, randomBytes(32));
  const sigHex = Buffer.from(sig).toString('hex');
  const pubHex = Buffer.from(keys.public_key).toString('hex');
  console.log(`✍️  Message signed with ML-DSA-65`);
  console.log(`   Message: ${message.slice(0, 80)}${message.length > 80 ? '...' : ''}`);
  console.log(`   Signature: ${sigHex.slice(0, 32)}...${sigHex.slice(-16)}`);
  console.log(`   Length: ${sig.length} bytes`);
  console.log(`\n   To verify:`);
  console.log(`   node verification/ml-dsa-signer.js verify "${message}" ${sigHex} ${pubHex}`);
  return { sig: sigHex, pub: pubHex };
}

function verify(message, sigHex, pubHex) {
  const msgBytes = Buffer.from(message, 'utf-8');
  const sig = Buffer.from(sigHex, 'hex');
  const pub = Buffer.from(pubHex, 'hex');
  const valid = ml_dsa65.verify(pub, msgBytes, sig);
  if (valid) {
    console.log(`✅ ML-DSA-65 signature VALID`);
    console.log(`   Message: ${message.slice(0, 80)}${message.length > 80 ? '...' : ''}`);
    console.log(`   Public key fingerprint: ${sha256Hex(pub).slice(0, 16)}`);
    return true;
  } else {
    console.log(`❌ ML-DSA-65 signature INVALID`);
    return false;
  }
}

function main() {
  const args = process.argv.slice(2);
  const cmd = args[0];

  if (cmd === 'keygen') {
    generateKeypair();
  } else if (cmd === 'sign') {
    const message = args.slice(1).join(' ') || 'CP8-ASH-0.2-attestation';
    sign(message);
  } else if (cmd === 'verify') {
    const message = args[1];
    const sig = args[2];
    const pub = args[3];
    if (!message || !sig || !pub) {
      console.error('Usage: verify <message> <sig_hex> <pub_hex>');
      process.exit(1);
    }
    const ok = verify(message, sig, pub);
    process.exit(ok ? 0 : 1);
  } else {
    console.log(`ML-DSA-65 (FIPS 204) Quantum-Resistant Signer
Usage:
  node verification/ml-dsa-signer.js keygen
  node verification/ml-dsa-signer.js sign <message>
  node verification/ml-dsa-signer.js verify <message> <sig_hex> <pub_hex>

Keyfile: ${KEY_FILE}
Algorithm: ML-DSA-65 (NIST FIPS 204)
Security level: NIST Level 3 (equivalent to AES-192)`);
  }
}

main();
