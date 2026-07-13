// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import {Strings} from "./StringCon.sol";

// Data-collection helper shared by every example harness. An action records a token's
// balance change with collect.gained("<token>", amount) (the token went up) or
// collect.spent("<token>", amount) (it went down) — amount is the RAW positive magnitude;
// the direction is the method name (and the effect's op). The engine appends collect.flush(),
// which reverts "FlashSyn: <token>=<raw> ..." for the parser (forge/forgeJson.py), which
// scales by token_info decimals. Nothing recorded -> "FlashSyn: 0". Deploy one per harness.
contract Collect {
    string private buf;

    function gained(string memory name, uint amount) external { _record(name, amount); }
    function spent(string memory name, uint amount) external { _record(name, amount); }

    function _record(string memory name, uint amount) private {
        if (bytes(buf).length != 0) {
            buf = Strings.append(buf, " ");
        }
        buf = Strings.append(string(abi.encodePacked(buf, name, "=")), amount);
    }

    function flush() external {
        if (bytes(buf).length == 0) {
            revert(Strings.append("FlashSyn: ", uint(0)));
        }
        revert(Strings.append("FlashSyn: ", buf));
    }
}
