# Integration: CP8 Humanoid Corrections → On-Chain Verification (HarmonicCoin)

## Flow
1. Robot produces motion frame / decision trace
2. CP8 lattice audits + applies correction (glyph-tagged, hash-sealed)
3. Corrected block is submitted as CP8 PoW-style proof (off-chain)
4. CP8Oracle.verifyProof() checks hash match + difficulty
5. On success → HarmonicCoin.mintForVerifiedBlock() awards 111 HHC to the submitter (or designated node)

## Why This Matters for Robotics
- Creates economic incentive for high-quality, verifiable corrections
- Makes robot behavior provenance-bound and replayable
- Allows third-party auditors (human or agent) to earn for work that actually improves physical AI safety/reliability

## Current Status
- CP8Oracle.sol and HarmonicCoin.sol live in ASIN-HHC-Collaboration (bridge to this repo)
- Merkle proof scripts already exist in Holbrook-CP8-HHC (scripts/build-merkle.py, verification/)
- Next: Adapt proof format for robot gait logs and test on Sepolia

This closes the loop: physical work (robot correction) → cryptographic proof → on-chain reward.