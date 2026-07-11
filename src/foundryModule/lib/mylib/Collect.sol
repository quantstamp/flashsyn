// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import {Strings} from "./StringCon.sol";

// Data-collection helper shared by every example harness. An action records named
// balance changes with collect.balanceChange("<token>", wholeTokenValue); the engine
// appends collect.flush(), which reverts "FlashSyn: <token>=<val> ..." for the collector
// parser (forge/forgeJson.py). Values are pre-scaled to whole tokens, so the parser reads
// integers; nothing recorded -> "FlashSyn: 0". Deploy one per harness in setUp().
contract Collect {
    string private buf;

    function balanceChange(string memory name, uint value) external {
        if (bytes(buf).length != 0) {
            buf = Strings.append(buf, " ");
        }
        buf = Strings.append(string(abi.encodePacked(buf, name, "=")), value);
    }

    function flush() external {
        if (bytes(buf).length == 0) {
            revert(Strings.append("FlashSyn: ", uint(0)));
        }
        revert(Strings.append("FlashSyn: ", buf));
    }
}
