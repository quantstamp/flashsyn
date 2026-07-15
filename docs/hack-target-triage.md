# Hack-target triage for FlashSyn

Working notes on candidate exploits to build as FlashSyn examples, and what to check for each.

**FlashSyn-fit rule of thumb.** FlashSyn fits a *smooth multivariate polynomial* over
**continuous amount parameters** and optimizes it. It fits when profit varies smoothly with
action *amounts* (price / NAV / exchange-rate manipulation). It does **not** fit when the exploit
is driven by a discrete *count* of calls, a logic/ordering bug, or a singularity (supply→0,
rounding-compound) — the polynomial can't represent those.

## Status table

| # | Target | Loss | Mechanism | FlashSyn fit | Status |
|---|--------|------|-----------|--------------|--------|
| — | Sky lending | — | OSM-delay + Chainlink, no reserve pricing | N/A (hardened) | assessed — not a target |
| 1 | **Lazy Summer** | $6.04M | donate stale Silo shares → ark NAV inflation → redeem | **Strong** | ✅ **built + verified** ($1.49M rediscovery) |
| 2 | Edel Finance | $403K | wGOOGLx exchange rate 78× via deposit/borrow loops | Moderate | greenlit — verify feasibility |
| 3 | NovaBox | $93.6K | dividend distributed before balance update (Ethereum) | Moderate | triaged |
| 4 | JB DeFi | $50K | "flashloan price manipulation" (protocol unidentified) | Unknown | queued — needs ID |
| 5 | Thetanuts | $105K net | redemption/integer math, supply reduced → ~0 | Poor–moderate | triaged (singularity) |
| 6 | Royal.io | $263K | 100 zero-value ERC1155 transfers manipulate accounting | **Poor** | not recommended |
| 7 | Ambient | $110.6K | surplus-collateral accounting, HotProxy/WarmPath/ColdPath op-cycling | **Poor** | not recommended |

## What to explore / check per candidate

### 2. Edel Finance (greenlit — verify first)
- **Chain**: unconfirmed. wGOOGLx = wrapped tokenised Google equity — likely NOT Ethereum. FlashSyn's `run.sh` supports ETH/BSC/Fantom/Polygon; if Edel is on Base/Arbitrum/an app-chain, add an RPC endpoint to `run.sh` first (see the Lazy Summer note that ETH was already supported).
- **Bug smoothness**: "78× via repeated deposit/borrow loops" smells like a compounding rounding/precision bug. Check whether the wGOOGLx exchange rate is a smooth function of a single deposit amount, or whether the 78× only appears after N discrete loops. If discrete-loop-driven → poor fit (like Thetanuts). If one big deposit moves the rate smoothly → buildable.
- **Actions if buildable**: `deposit → borrow` (amounts as params), with the wGOOGLx exchange-rate read as the manipulated quantity. Model over-borrow as profit (walk-away, like the T1 borrow); the health/rate check caps it on-chain.
- **Get**: exploit tx hash + block, wGOOGLx wrapper contract + its exchange-rate function, the Edel lending pool address, borrowed asset.

### 3. NovaBox (moderate — Ethereum)
- **Mechanism**: dividends credited before balance update. Deposit small NOVA (snapshot dividend at small share) → large ETH deposit (inflate actual share, system still uses stale share) → claim "phantom dividends".
- **Fit caveat**: profit is amount-driven (phantom dividend scales with deposit sizes) but the distribute-before-update ordering can make it threshold-y. Worth an attempt if greenlit.
- **Get**: exploit tx + block, NovaBox reward-pool contract, deposit/withdraw/claim signatures, NOVA token.

### 4. JB DeFi (queued — identify first)
- "JB DeFi protocol" is ambiguous (JuiceBox? Jimbo? other?). $50K, "flashloan price manipulation". **First step: identify the actual protocol + exploit tx + chain**, then re-triage. If it's genuine AMM price manipulation on a supported chain, likely a good fit.

### 5–7. Thetanuts / Royal.io / Ambient (not recommended)
- **Thetanuts**: redemption/integer math with supply→0 is a *singularity* — polynomial approximation fails near it. Would need a custom reformulation; skip unless specifically wanted.
- **Royal.io**: driven by the *count* of zero-value ERC1155 transfers (amounts = 0). FlashSyn optimizes amounts, not call counts — structural mismatch. Document as "out of FlashSyn's class" rather than build.
- **Ambient**: accounting bug exploited by *cycling* HotProxy/WarmPath/ColdPath operations — discrete op-sequence, not amount-driven. Same mismatch as Royal.io.

## General reminders for any build
- Confirm the **chain** is in `run.sh` (ETH/BSC/Fantom/Polygon); else add the endpoint.
- Fork at the block **just before** the exploit tx.
- Reconstruct the exact mechanism from the tx (`eth_getLogs` for token transfers; verified source via Blockscout — `debug_traceTransaction` is blocked on the free Alchemy tier).
- Fund the attacker with the flash-loan capital + any pre-accumulated assets in `setUp` (masterMinter for USDC, `vm.store`/`tip` for others; some proxy/COMP-style tokens need `vm.store` at the verified balance slot because `tip` can't find it).
- Model manipulation actions with zero params like Euler's `donate`, and realize profit through amount-parameterized swaps/redeems.
- anvil (`--fast-using-anvil`) can be flaky forking very recent blocks — fall back to plain `synthesize`.
