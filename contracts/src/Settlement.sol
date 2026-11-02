// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {HHCWorkCredit} from "./HHCWorkCredit.sol";
import {AdminHandoff} from "./AdminHandoff.sol";

/// @title ASIN-HHC Settlement
/// @notice Mints HHCW, a work token for verified contribution, from an EIP-712
///         attestation signed by SETTLER_ROLE.
///         Split is exact: worker 9000 bps, each of the two verifiers 500 bps.
///         The three amounts must add up to `contributionMinor`. Dust reverts.
contract Settlement is AdminHandoff, Pausable, EIP712 {
    using ECDSA for bytes32;

    bytes32 public constant SETTLER_ROLE = keccak256("SETTLER_ROLE");
    bytes32 public constant ANCHOR_ROLE = keccak256("ANCHOR_ROLE");

    uint16 public constant WORKER_SHARE_BPS = 9000;
    uint16 public constant VERIFIER_SHARE_BPS = 500;
    uint16 public constant BPS_DENOM = 10000;

    bytes32 public constant SETTLEMENT_TYPEHASH = keccak256(
        "SettlementAttestation(bytes32 settlementId,address worker,uint256 workerAmount,address verifier1,uint256 verifier1Amount,address verifier2,uint256 verifier2Amount,uint256 contributionMinor,bytes32 receiptRoot)"
    );

    HHCWorkCredit public immutable token;

    mapping(bytes32 => bool) public settled;
    mapping(uint256 => bytes32) public anchors;
    uint256 public anchorCount;

    event Settled(
        bytes32 indexed settlementId,
        address indexed worker,
        address verifier1,
        address verifier2,
        uint256 workerAmount,
        uint256 verifier1Amount,
        uint256 verifier2Amount,
        uint256 contributionMinor,
        bytes32 receiptRoot
    );
    event MerkleAnchored(uint256 indexed sequence, bytes32 root, address indexed submitter);

    error AlreadySettled(bytes32 settlementId);
    error BadSplit(uint256 workerAmount, uint256 v1, uint256 v2, uint256 contributionMinor);
    error BadSigner(address recovered);
    error ZeroAmount();

    constructor(address admin, HHCWorkCredit token_) AdminHandoff(admin) EIP712("ASIN-HHC Settlement", "1") {
        if (address(token_) == address(0)) revert ZeroAddress();
        token = token_;
        _grantRole(SETTLER_ROLE, admin);
        _grantRole(ANCHOR_ROLE, admin);
    }

    function _afterAdminAccepted(address previous, address next) internal override {
        _grantRole(SETTLER_ROLE, next);
        _grantRole(ANCHOR_ROLE, next);
        if (previous != next) {
            _revokeRole(SETTLER_ROLE, previous);
            _revokeRole(ANCHOR_ROLE, previous);
        }
    }

    /// @notice Settle and mint. `settlementId` is bytes32 (for example keccak256 of the string id).
    /// @param signature EIP-712 signature from an address with SETTLER_ROLE
    function settle(
        bytes32 settlementId,
        address worker,
        uint256 workerAmount,
        address verifier1,
        uint256 verifier1Amount,
        address verifier2,
        uint256 verifier2Amount,
        uint256 contributionMinor,
        bytes32 receiptRoot,
        bytes calldata signature
    ) external whenNotPaused {
        if (settled[settlementId]) revert AlreadySettled(settlementId);
        if (worker == address(0) || verifier1 == address(0) || verifier2 == address(0)) {
            revert ZeroAddress();
        }
        if (contributionMinor == 0) revert ZeroAmount();
        uint256 expectedWorker = (contributionMinor * WORKER_SHARE_BPS) / BPS_DENOM;
        uint256 expectedVerifier = (contributionMinor * VERIFIER_SHARE_BPS) / BPS_DENOM;
        if (
            workerAmount != expectedWorker || verifier1Amount != expectedVerifier
                || verifier2Amount != expectedVerifier
                || workerAmount + verifier1Amount + verifier2Amount != contributionMinor
        ) {
            revert BadSplit(workerAmount, verifier1Amount, verifier2Amount, contributionMinor);
        }

        bytes32 structHash = keccak256(
            abi.encode(
                SETTLEMENT_TYPEHASH,
                settlementId,
                worker,
                workerAmount,
                verifier1,
                verifier1Amount,
                verifier2,
                verifier2Amount,
                contributionMinor,
                receiptRoot
            )
        );
        address signer = _hashTypedDataV4(structHash).recover(signature);
        if (!hasRole(SETTLER_ROLE, signer)) revert BadSigner(signer);

        settled[settlementId] = true;

        token.mint(worker, workerAmount);
        token.mint(verifier1, verifier1Amount);
        token.mint(verifier2, verifier2Amount);

        emit Settled(
            settlementId,
            worker,
            verifier1,
            verifier2,
            workerAmount,
            verifier1Amount,
            verifier2Amount,
            contributionMinor,
            receiptRoot
        );
    }

    /// @notice Commit a Merkle root over mesh receipt hashes.
    function merkleAnchor(bytes32 root) external onlyRole(ANCHOR_ROLE) whenNotPaused {
        uint256 seq = ++anchorCount;
        anchors[seq] = root;
        emit MerkleAnchored(seq, root, msg.sender);
    }

    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    function domainSeparator() external view returns (bytes32) {
        return _domainSeparatorV4();
    }
}
