// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import {Collect} from "./Collect.sol";

// Base for every FlashSyn example harness. It declares and deploys the `collect` helper that
// the engine's generated data collectors call (collect.gained/spent/flush); every example's
// attack.t.sol inherits it (`contract X is DSTest, stdCheats, FlashSynHarness`).
//
// `collect` lives here, not in each attack.t.sol, so it CANNOT be accidentally dropped: the
// generated Solidity depends on it, and an author deleting the declaration or its deployment
// would break collection with a cryptic solc error. It is deployed in the state-variable
// initializer (at construction, before setUp), so an example needs no boilerplate for it.
abstract contract FlashSynHarness {
    Collect internal collect = new Collect();
}
