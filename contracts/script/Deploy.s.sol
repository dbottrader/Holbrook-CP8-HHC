// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {HHCWorkCredit} from "../src/HHCWorkCredit.sol";
import {Settlement} from "../src/Settlement.sol";

/// @notice Base Sepolia / local Anvil deploy.
///         The broadcaster is admin and owner for now. Hand the roles off later
///         with proposeAdmin, then acceptAdmin, after `defaultAdminDelay()`.
///         PRIVATE_KEY stays in the shell. Do not commit it. Do not use this
///         script for mainnet; use script/DeployMainnet.s.sol.
///
///         Source verification, from `contracts/` after the broadcast:
///         forge verify-contract --chain base-sepolia --verifier etherscan \
///           --etherscan-api-key "$BASESCAN_API_KEY" \
///           --constructor-args "$(cast abi-encode "constructor(address)" "$ADMIN")" \
///           "$TOKEN_ADDR" src/HHCWorkCredit.sol:HHCWorkCredit
///         forge verify-contract --chain base-sepolia --verifier etherscan \
///           --etherscan-api-key "$BASESCAN_API_KEY" \
///           --constructor-args "$(cast abi-encode "constructor(address,address)" "$ADMIN" "$TOKEN_ADDR")" \
///           "$SETTLEMENT_ADDR" src/Settlement.sol:Settlement
contract Deploy is Script {
    function run() external {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(pk);

        vm.startBroadcast(pk);
        HHCWorkCredit token = new HHCWorkCredit(deployer);
        Settlement settlement = new Settlement(deployer, token);
        token.grantRole(token.MINTER_ROLE(), address(settlement));
        vm.stopBroadcast();

        console2.log("HHCWorkCredit", address(token));
        console2.log("Settlement", address(settlement));
        console2.log("admin", deployer);
    }
}
