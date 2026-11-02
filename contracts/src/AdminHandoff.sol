// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AccessControlDefaultAdminRules} from "@openzeppelin/contracts/access/extensions/AccessControlDefaultAdminRules.sol";

/// @notice Two-step admin handoff for HHCW stewardship.
///         `owner()` is the default admin (IERC-5313). Propose, wait out the
///         OpenZeppelin delay, then the proposed account accepts. Accept moves
///         DEFAULT_ADMIN, OWNER_ROLE, and PAUSER_ROLE. The previous admin loses them.
abstract contract AdminHandoff is AccessControlDefaultAdminRules {
    bytes32 public constant OWNER_ROLE = keccak256("OWNER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    error ZeroAddress();

    /// @dev One day matches a deliberate handoff. Tests warp past `defaultAdminDelay()`.
    uint48 public constant HANDOFF_DELAY = 1 days;

    constructor(address initialAdmin) AccessControlDefaultAdminRules(HANDOFF_DELAY, initialAdmin) {
        if (initialAdmin == address(0)) revert ZeroAddress();
        _grantRole(OWNER_ROLE, initialAdmin);
        _grantRole(PAUSER_ROLE, initialAdmin);
    }

    /// @notice Schedule `next` as the new admin. Caller must be the current admin.
    function proposeAdmin(address next) external {
        if (next == address(0)) revert ZeroAddress();
        beginDefaultAdminTransfer(next);
    }

    /// @notice Proposed account accepts and takes admin, owner, and pauser.
    function acceptAdmin() external {
        address previous = defaultAdmin();
        acceptDefaultAdminTransfer();
        _grantRole(OWNER_ROLE, msg.sender);
        _grantRole(PAUSER_ROLE, msg.sender);
        if (previous != msg.sender) {
            _revokeRole(OWNER_ROLE, previous);
            _revokeRole(PAUSER_ROLE, previous);
            _afterAdminAccepted(previous, msg.sender);
        }
    }

    /// @dev Settlement moves settler and anchor roles here. The token has none.
    function _afterAdminAccepted(address previous, address next) internal virtual {}
}
