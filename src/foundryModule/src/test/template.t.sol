// SPDX-License-Identifier: MIT
pragma solidity >0.4.21;

import {DSTest} from "ds-test/test.sol";
import {Vm} from "forge-std/Vm.sol";
import {stdCheats} from "forge-std/stdlib.sol";
import {Strings} from "mylib/StringCon.sol";


//TODO: 1. Define all needed interfaces & structs below. Reference the example foundry script as needed throughout.

interface IProtocol {
    // TODO
}

struct ProtocolStruct {
    // TODO, as needed
    uint x;
}

contract Protocol is DSTest, stdCheats {
    Vm internal constant vm = Vm(HEVM_ADDRESS);
    address payable constant attacker = payable(address(uint160(uint256(keccak256(abi.encodePacked("attacker"))))));

    // TODO: 2. Define all state variables needed in the testExample() functions
        // This will include state variables for contracts used by protocol actions as well as the requeired number of attacker addresses.
    

    // TODO 3. Define the setUp() function. This function runs before each test.
        // Ensure that proper approvals are given at this step.

    function setUp() public {
        vm.startPrank(attacker);
        //EXAMPLE: USDC.approve(address(), type(uint256).max);
    }

    // TODO 4. Define this profitSummary function to append & print out the balance of the tokens in consideration for profits.
    function profitSummary() public view returns (string memory) {
        //EXAMPLE: string memory profitSummaryString = Strings.append("FlashSyn: ", "".balanceOf(address(attacker)) / 1e6);
        string memory profitSummaryString = "";
        return profitSummaryString;
    }

    // TODO 5. Define a testExample() functions for each ProtocolAction below. They first one should be named `testExample0()`.
        // The function call of the Action itself should be written in between the separator logs.
        // If there are additional calls that the Action is dependent on prior to it being called, call those functions outside of the Separator logs
        // Be sure to include the empty string revert at the end of the functions
        // Use startPrank() and stopPrank() to switch accounts as needed. Usually, all of the testExamples will be run from the attacker account,
            //however more complicated Actions may require more accounts

    function testExample0() public {
        // TODO Write function calls that the Action is dependent on here
            // e.g. a deposit before the minting of protocol tokens

        emit log("=================== Separator ==================");
        
        // TODO Write Protocol Action function call

        emit log("=================== Separator ==================");
        revert("");
    }

    // TODO 6. Define the remaining `testExample()` functions for each ProtocolAction.
}