// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {HHCWorkCredit} from "../src/HHCWorkCredit.sol";
import {Settlement} from "../src/Settlement.sol";

/// @notice Replace the Settlement contract and keep the existing HHCW token.
///         Deploys the new Settlement (with the SameAddress guard), grants it
///         MINTER_ROLE on the token, and revokes MINTER_ROLE from the old one,
///         so only the new contract can mint. Balances already minted stay.
///
///         Run by the token admin only. PRIVATE_KEY stays in the shell.
///         See contracts/REDEPLOY_SETTLEMENT.md for the full steps.
///
///         Env: PRIVATE_KEY, TOKEN_ADDR (HHCW), OLD_SETTLEMENT (current Settlement).
contract RedeploySettlement is Script {
    function run() external {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        HHCWorkCredit token = HHCWorkCredit(vm.envAddress("TOKEN_ADDR"));
        address oldSettlement = vm.envAddress("OLD_SETTLEMENT");
        address admin = vm.addr(pk);
        bytes32 minter = token.MINTER_ROLE();
        require(token.hasRole(token.DEFAULT_ADMIN_ROLE(), admin), "signer is not the token admin");

        vm.startBroadcast(pk);
        Settlement settlement = new Settlement(admin, token);
        token.grantRole(minter, address(settlement));
        if (oldSettlement != address(0) && token.hasRole(minter, oldSettlement)) {
            token.revokeRole(minter, oldSettlement);
        }
        vm.stopBroadcast();

        require(token.hasRole(minter, address(settlement)), "new settlement cannot mint");
        require(!token.hasRole(minter, oldSettlement), "old settlement can still mint");
        console2.log("Settlement", address(settlement));
        console2.log("HHCWorkCredit", address(token));
        console2.log("revoked MINTER_ROLE from", oldSettlement);
    }
}
