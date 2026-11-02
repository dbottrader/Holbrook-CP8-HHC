// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {IAccessControlDefaultAdminRules} from
    "@openzeppelin/contracts/access/extensions/IAccessControlDefaultAdminRules.sol";
import {HHCWorkCredit} from "../src/HHCWorkCredit.sol";
import {Settlement} from "../src/Settlement.sol";

contract AdminHandoffTest is Test {
    HHCWorkCredit internal token;
    Settlement internal settlement;
    address internal admin = address(0xA11CE);
    address internal next = address(0xB0B);
    address internal stranger = address(0xBAD);

    function setUp() public {
        vm.startPrank(admin);
        token = new HHCWorkCredit(admin);
        settlement = new Settlement(admin, token);
        token.grantRole(token.MINTER_ROLE(), address(settlement));
        vm.stopPrank();
    }

    function test_propose_and_accept_moves_roles_and_old_admin_loses_them() public {
        vm.prank(admin);
        settlement.proposeAdmin(next);
        (address pending,) = settlement.pendingDefaultAdmin();
        assertEq(pending, next);

        vm.warp(block.timestamp + settlement.defaultAdminDelay() + 1);
        vm.prank(next);
        settlement.acceptAdmin();

        assertEq(settlement.defaultAdmin(), next);
        assertEq(settlement.owner(), next);
        assertTrue(settlement.hasRole(settlement.DEFAULT_ADMIN_ROLE(), next));
        assertTrue(settlement.hasRole(settlement.OWNER_ROLE(), next));
        assertTrue(settlement.hasRole(settlement.PAUSER_ROLE(), next));
        assertTrue(settlement.hasRole(settlement.SETTLER_ROLE(), next));
        assertTrue(settlement.hasRole(settlement.ANCHOR_ROLE(), next));

        assertFalse(settlement.hasRole(settlement.DEFAULT_ADMIN_ROLE(), admin));
        assertFalse(settlement.hasRole(settlement.OWNER_ROLE(), admin));
        assertFalse(settlement.hasRole(settlement.PAUSER_ROLE(), admin));
        assertFalse(settlement.hasRole(settlement.SETTLER_ROLE(), admin));
        assertFalse(settlement.hasRole(settlement.ANCHOR_ROLE(), admin));

        vm.prank(admin);
        vm.expectRevert();
        settlement.pause();

        vm.prank(next);
        settlement.pause();
    }

    function test_wrong_acceptor_reverts() public {
        vm.prank(admin);
        settlement.proposeAdmin(next);
        vm.warp(block.timestamp + settlement.defaultAdminDelay() + 1);

        vm.prank(stranger);
        vm.expectRevert(
            abi.encodeWithSelector(
                IAccessControlDefaultAdminRules.AccessControlInvalidDefaultAdmin.selector, stranger
            )
        );
        settlement.acceptAdmin();

        assertEq(settlement.owner(), admin);
        assertTrue(settlement.hasRole(settlement.DEFAULT_ADMIN_ROLE(), admin));
    }

    function test_accept_before_delay_reverts() public {
        vm.prank(admin);
        settlement.proposeAdmin(next);
        (, uint48 schedule) = settlement.pendingDefaultAdmin();

        vm.prank(next);
        vm.expectRevert(
            abi.encodeWithSelector(
                IAccessControlDefaultAdminRules.AccessControlEnforcedDefaultAdminDelay.selector, schedule
            )
        );
        settlement.acceptAdmin();
        assertEq(settlement.owner(), admin);
    }

    function test_token_handoff_keeps_minter_on_settlement() public {
        vm.prank(admin);
        token.proposeAdmin(next);
        vm.warp(block.timestamp + token.defaultAdminDelay() + 1);
        vm.prank(next);
        token.acceptAdmin();

        assertEq(token.owner(), next);
        assertFalse(token.hasRole(token.DEFAULT_ADMIN_ROLE(), admin));
        assertFalse(token.hasRole(token.OWNER_ROLE(), admin));
        assertFalse(token.hasRole(token.PAUSER_ROLE(), admin));
        assertTrue(token.hasRole(token.DEFAULT_ADMIN_ROLE(), next));
        assertTrue(token.hasRole(token.MINTER_ROLE(), address(settlement)));
    }
}
