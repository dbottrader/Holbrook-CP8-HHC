// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {HHCWorkCredit} from "../src/HHCWorkCredit.sol";
import {Settlement} from "../src/Settlement.sol";

contract SettlementTest is Test {
    HHCWorkCredit internal token;
    Settlement internal settlement;

    address internal admin = address(0xA11CE);
    address internal settler;
    uint256 internal settlerKey;
    address internal worker;
    address internal v1;
    address internal v2;
    address internal stranger;

    bytes32 internal constant SETTLEMENT_TYPEHASH = keccak256(
        "SettlementAttestation(bytes32 settlementId,address worker,uint256 workerAmount,address verifier1,uint256 verifier1Amount,address verifier2,uint256 verifier2Amount,uint256 contributionMinor,bytes32 receiptRoot)"
    );

    function setUp() public {
        settlerKey = 0xBEEF;
        settler = vm.addr(settlerKey);

        vm.startPrank(admin);
        token = new HHCWorkCredit(admin);
        settlement = new Settlement(admin, token);
        token.grantRole(token.MINTER_ROLE(), address(settlement));
        settlement.grantRole(settlement.SETTLER_ROLE(), settler);
        vm.stopPrank();

        worker = makeAddr("worker");
        v1 = makeAddr("verifier1");
        v2 = makeAddr("verifier2");
        stranger = makeAddr("stranger");
    }

    function _split(uint256 total) internal pure returns (uint256 w, uint256 a1, uint256 a2) {
        w = (total * 9000) / 10000;
        a1 = (total * 500) / 10000;
        a2 = (total * 500) / 10000;
    }

    function _sign(bytes32 settlementId, uint256 total, bytes32 receiptRoot)
        internal
        view
        returns (uint256 w, uint256 a1, uint256 a2, bytes memory sig)
    {
        (w, a1, a2) = _split(total);
        bytes32 structHash = keccak256(
            abi.encode(
                SETTLEMENT_TYPEHASH, settlementId, worker, w, v1, a1, v2, a2, total, receiptRoot
            )
        );
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", settlement.domainSeparator(), structHash));
        (uint8 vv, bytes32 r, bytes32 s) = vm.sign(settlerKey, digest);
        sig = abi.encodePacked(r, s, vv);
    }

    function test_settle_mints_90_5_5_split() public {
        bytes32 sid = keccak256("settle-1");
        uint256 total = 1000;
        bytes32 root = keccak256("receipts");
        (uint256 w, uint256 a1, uint256 a2, bytes memory sig) = _sign(sid, total, root);
        assertEq(w, 900);
        assertEq(a1, 50);
        assertEq(a2, 50);

        settlement.settle(sid, worker, w, v1, a1, v2, a2, total, root, sig);

        assertEq(token.balanceOf(worker), 900);
        assertEq(token.balanceOf(v1), 50);
        assertEq(token.balanceOf(v2), 50);
        assertEq(token.balanceOf(worker) + token.balanceOf(v1) + token.balanceOf(v2), total);
        assertTrue(settlement.settled(sid));
    }

    function test_dust_split_reverts() public {
        bytes32 sid = keccak256("settle-dust");
        uint256 total = 101;
        bytes32 root = bytes32(uint256(1));
        (uint256 w, uint256 a1, uint256 a2) = _split(total);
        assertEq(w, 90);
        assertEq(a1, 5);
        assertEq(a2, 5);
        assertEq(w + a1 + a2, 100);

        bytes32 structHash =
            keccak256(abi.encode(SETTLEMENT_TYPEHASH, sid, worker, w, v1, a1, v2, a2, total, root));
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", settlement.domainSeparator(), structHash));
        (uint8 vv, bytes32 r, bytes32 s) = vm.sign(settlerKey, digest);
        bytes memory sig = abi.encodePacked(r, s, vv);

        vm.expectRevert(abi.encodeWithSelector(Settlement.BadSplit.selector, w, a1, a2, total));
        settlement.settle(sid, worker, w, v1, a1, v2, a2, total, root, sig);
    }

    function test_replay_reverts() public {
        bytes32 sid = keccak256("settle-replay");
        uint256 total = 1000;
        bytes32 root = bytes32(uint256(2));
        (uint256 w, uint256 a1, uint256 a2, bytes memory sig) = _sign(sid, total, root);
        settlement.settle(sid, worker, w, v1, a1, v2, a2, total, root, sig);

        vm.expectRevert(abi.encodeWithSelector(Settlement.AlreadySettled.selector, sid));
        settlement.settle(sid, worker, w, v1, a1, v2, a2, total, root, sig);
    }

    function test_wrong_signer_reverts() public {
        bytes32 sid = keccak256("settle-bad-sig");
        uint256 total = 1000;
        bytes32 root = bytes32(uint256(3));
        (uint256 w, uint256 a1, uint256 a2,) = _sign(sid, total, root);

        uint256 badKey = 0xDEAD;
        bytes32 structHash =
            keccak256(abi.encode(SETTLEMENT_TYPEHASH, sid, worker, w, v1, a1, v2, a2, total, root));
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", settlement.domainSeparator(), structHash));
        (uint8 vv, bytes32 r, bytes32 s) = vm.sign(badKey, digest);
        bytes memory sig = abi.encodePacked(r, s, vv);

        vm.expectRevert(abi.encodeWithSelector(Settlement.BadSigner.selector, vm.addr(badKey)));
        settlement.settle(sid, worker, w, v1, a1, v2, a2, total, root, sig);
    }

    function test_bad_split_reverts() public {
        bytes32 sid = keccak256("settle-bad-split");
        uint256 total = 1000;
        bytes32 root = bytes32(uint256(4));
        uint256 w = 800;
        uint256 a1 = 100;
        uint256 a2 = 100;
        bytes32 structHash =
            keccak256(abi.encode(SETTLEMENT_TYPEHASH, sid, worker, w, v1, a1, v2, a2, total, root));
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", settlement.domainSeparator(), structHash));
        (uint8 vv, bytes32 r, bytes32 s) = vm.sign(settlerKey, digest);
        bytes memory sig = abi.encodePacked(r, s, vv);

        vm.expectRevert(abi.encodeWithSelector(Settlement.BadSplit.selector, w, a1, a2, total));
        settlement.settle(sid, worker, w, v1, a1, v2, a2, total, root, sig);
    }

    function test_amounts_must_sum_to_contribution() public {
        bytes32 sid = keccak256("settle-sum");
        uint256 total = 1000;
        bytes32 root = bytes32(uint256(5));
        uint256 w = 900;
        uint256 a1 = 50;
        uint256 a2 = 40;
        bytes32 structHash =
            keccak256(abi.encode(SETTLEMENT_TYPEHASH, sid, worker, w, v1, a1, v2, a2, total, root));
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", settlement.domainSeparator(), structHash));
        (uint8 vv, bytes32 r, bytes32 s) = vm.sign(settlerKey, digest);
        bytes memory sig = abi.encodePacked(r, s, vv);

        vm.expectRevert(abi.encodeWithSelector(Settlement.BadSplit.selector, w, a1, a2, total));
        settlement.settle(sid, worker, w, v1, a1, v2, a2, total, root, sig);
    }

    function test_unequal_verifiers_revert() public {
        bytes32 sid = keccak256("settle-unequal");
        uint256 total = 1000;
        bytes32 root = bytes32(uint256(9));
        uint256 w = 900;
        uint256 a1 = 60;
        uint256 a2 = 40;
        bytes32 structHash =
            keccak256(abi.encode(SETTLEMENT_TYPEHASH, sid, worker, w, v1, a1, v2, a2, total, root));
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", settlement.domainSeparator(), structHash));
        (uint8 vv, bytes32 r, bytes32 s) = vm.sign(settlerKey, digest);
        bytes memory sig = abi.encodePacked(r, s, vv);

        vm.expectRevert(abi.encodeWithSelector(Settlement.BadSplit.selector, w, a1, a2, total));
        settlement.settle(sid, worker, w, v1, a1, v2, a2, total, root, sig);
    }

    function test_pause_blocks_settle_and_anchor() public {
        vm.prank(admin);
        settlement.pause();

        bytes32 sid = keccak256("settle-paused");
        uint256 total = 1000;
        bytes32 root = bytes32(uint256(6));
        (uint256 w, uint256 a1, uint256 a2, bytes memory sig) = _sign(sid, total, root);

        vm.expectRevert();
        settlement.settle(sid, worker, w, v1, a1, v2, a2, total, root, sig);

        vm.prank(admin);
        vm.expectRevert();
        settlement.merkleAnchor(keccak256("x"));
    }

    function test_pause_blocks_token_transfer() public {
        bytes32 sid = keccak256("settle-then-pause");
        uint256 total = 1000;
        bytes32 root = bytes32(uint256(7));
        (uint256 w, uint256 a1, uint256 a2, bytes memory sig) = _sign(sid, total, root);
        settlement.settle(sid, worker, w, v1, a1, v2, a2, total, root, sig);

        vm.prank(admin);
        token.pause();

        vm.prank(worker);
        vm.expectRevert();
        token.transfer(v1, 1);
    }

    function test_merkle_anchor() public {
        bytes32 root = keccak256("chain-root-1");
        vm.prank(admin);
        settlement.merkleAnchor(root);
        assertEq(settlement.anchorCount(), 1);
        assertEq(settlement.anchors(1), root);

        bytes32 root2 = keccak256("chain-root-2");
        vm.prank(admin);
        settlement.merkleAnchor(root2);
        assertEq(settlement.anchorCount(), 2);
        assertEq(settlement.anchors(2), root2);
    }

    function test_anchor_requires_role() public {
        vm.prank(stranger);
        vm.expectRevert();
        settlement.merkleAnchor(keccak256("nope"));
    }

    function test_double_settlement_different_ids_ok() public {
        uint256 total = 2000;
        bytes32 root = bytes32(uint256(8));
        bytes32 sid1 = keccak256("a");
        bytes32 sid2 = keccak256("b");
        (uint256 w, uint256 a1, uint256 a2, bytes memory sig1) = _sign(sid1, total, root);
        assertEq(w, 1800);
        assertEq(a1, 100);
        assertEq(a2, 100);
        settlement.settle(sid1, worker, w, v1, a1, v2, a2, total, root, sig1);

        (,,, bytes memory sig2) = _sign(sid2, total, root);
        settlement.settle(sid2, worker, w, v1, a1, v2, a2, total, root, sig2);

        assertEq(token.balanceOf(worker), w * 2);
        assertEq(token.balanceOf(v1), a1 * 2);
        assertEq(token.balanceOf(v2), a2 * 2);
    }

    function test_only_settlement_can_mint() public {
        vm.prank(stranger);
        vm.expectRevert();
        token.mint(worker, 1);
    }
}
