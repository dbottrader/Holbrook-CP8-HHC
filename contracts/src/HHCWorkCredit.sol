// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {AdminHandoff} from "./AdminHandoff.sol";

/// @title HHC Work Credit (HHCW)
/// @notice Work token for verified contribution. Mint is limited to MINTER_ROLE
///         (the Settlement contract). Units are integers.
contract HHCWorkCredit is ERC20, AdminHandoff, Pausable {
    bytes32 public constant MINTER_ROLE = keccak256("MINTER_ROLE");

    constructor(address admin) ERC20("HHC Work Credit", "HHCW") AdminHandoff(admin) {}

    /// @dev 18 decimals keeps ERC-20 tooling able to display integer contribution units.
    function decimals() public pure override returns (uint8) {
        return 18;
    }

    function mint(address to, uint256 amount) external onlyRole(MINTER_ROLE) whenNotPaused {
        require(to != address(0), "to=0");
        require(amount > 0, "amount=0");
        _mint(to, amount);
    }

    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    function _update(address from, address to, uint256 value) internal override whenNotPaused {
        super._update(from, to, value);
    }
}
