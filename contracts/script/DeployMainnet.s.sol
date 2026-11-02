// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {HHCWorkCredit} from "../src/HHCWorkCredit.sol";
import {Settlement} from "../src/Settlement.sol";

/// @notice Mainnet deploy. ADMIN_ADDRESS is the admin and owner at construction.
///         The broadcaster must be that account, via `forge script --ledger`
///         or an unlocked browser-wallet sender. This file does not read a key.
///
///         forge script script/DeployMainnet.s.sol:DeployMainnet \
///           --rpc-url "$BASE_RPC_URL" --ledger --sender "$ADMIN_ADDRESS" --broadcast
///
///         Browser-wallet RPC (account unlocked for ADMIN_ADDRESS):
///         forge script script/DeployMainnet.s.sol:DeployMainnet \
///           --rpc-url "$BASE_RPC_URL" --unlocked --sender "$ADMIN_ADDRESS" --broadcast
///
///         forge verify-contract --chain base --verifier etherscan \
///           --etherscan-api-key "$BASESCAN_API_KEY" \
///           --constructor-args "$(cast abi-encode "constructor(address)" "$ADMIN_ADDRESS")" \
///           "$TOKEN_ADDR" src/HHCWorkCredit.sol:HHCWorkCredit
///         forge verify-contract --chain base --verifier etherscan \
///           --etherscan-api-key "$BASESCAN_API_KEY" \
///           --constructor-args "$(cast abi-encode "constructor(address,address)" "$ADMIN_ADDRESS" "$TOKEN_ADDR")" \
///           "$SETTLEMENT_ADDR" src/Settlement.sol:Settlement
contract DeployMainnet is Script {
    error BroadcasterIsNotAdmin(address broadcaster, address admin);

    function run() external {
        address admin = vm.envAddress("ADMIN_ADDRESS");
        vm.startBroadcast();
        if (msg.sender != admin) revert BroadcasterIsNotAdmin(msg.sender, admin);
        HHCWorkCredit token = new HHCWorkCredit(admin);
        Settlement settlement = new Settlement(admin, token);
        token.grantRole(token.MINTER_ROLE(), address(settlement));
        vm.stopBroadcast();

        console2.log("HHCWorkCredit", address(token));
        console2.log("Settlement", address(settlement));
        console2.log("admin", admin);
    }
}
