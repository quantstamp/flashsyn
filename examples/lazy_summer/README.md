# Lazy Summer Protocol exploit (Summer.fi)

The [Lazy Summer Protocol exploit](https://etherscan.io/tx/0x0db528c44f23fc7fa4544684a2fab81096450a14aae8bc89f42cd0592d43da12)
(6 Jul 2026, ~$6.04M), as a worked FlashSyn rediscovery. Like `examples/harvest_usdt/`
and `examples/euler/`, this is a **real exploit** the tool re-derives — a vault-NAV /
share-price manipulation, the same archetype as Harvest.

The **FleetCommander** `LazyVault_LowerRisk_USDC` (`0x98C49e13`) is an ERC4626 USDC vault
that allocates deposits across many **Arks** (yield adapters). Its `totalAssets()` is the sum
of every active ark's `totalAssets()`. One ark — `SiloManagedVaultArk` (`0x61d70630`) —
reports:

```solidity
function totalAssets() returns (uint256) {
    return siloVault.convertToAssets(siloVault.balanceOf(address(this)));
}
```

The Silo "Varlamore USDC Growth" vault (`0x8399c8fc`) it wraps was impaired by the Nov-2025
Stream Finance collapse but its on-chain share price was **never marked down**, so it reports a
stale, inflated USDC-per-share. The ark had been offboarded (deposit cap set to 0) yet was left
in the vault's **active NAV set**. So **transferring (donating) Silo shares directly into the
ark** raises `ark.totalAssets()` by `convertToAssets(donated)` — inflating the whole vault's
NAV with nothing real backing it.

Chain: Ethereum mainnet, fork block **25471347** (the block before the exploit tx). Capital:
70,000,000 USDC (flash-loan for the deposit) + pre-accumulated impaired Silo shares (bought
cheap over months; real value ~0, so not counted against profit).

## Three actions

| action | in → out | call |
| --- | --- | --- |
| `fleet_deposit` | USDC → LVUSDC shares | `FLEET.deposit(·, attacker)` |
| `donate_silo`   | Silo shares → (inflates ark NAV) | `SILO.transfer(ARK, ·)` |
| `fleet_redeem`  | LVUSDC shares → USDC | `FLEET.redeem(·, attacker, attacker)` |

`donate_silo` produces no token for the attacker; its effect surfaces through `fleet_redeem`'s
larger USDC output in the sampled sequences (the same way Harvest's Curve manipulation surfaces
through the vault redeem). The NAV inflation is verified: on the fork the share price jumps
**1.066484 → 1.168444 (+9.6%)** on a donation, matching the post-mortem's 1.0665 → 1.1678.

## Run it

```sh
python3 flashsyn.py compile    lazy_summer
python3 flashsyn.py collect    lazy_summer --fast-using-anvil
python3 flashsyn.py synthesize lazy_summer > run.log
```

(Use plain `synthesize` — anvil can be flaky forking this very recent block; synthesis is
optimizer-bound so it costs little. `validate` marks `fleet_redeem` as failing because it smoke-
tests each action in isolation and redeem needs shares from a prior deposit — in real sequences
it runs after `fleet_deposit`.)

## Result (verified end-to-end)

FlashSyn **rediscovers the exploit** — the winning vector is exactly the attack:

```
fleet_deposit → donate_silo → fleet_redeem
Best Profit  1,491,168   Parameters [49575195, 25048828125, 41494141]
```

i.e. deposit ~$49.6M USDC → mint shares at ~1.0665 → donate ~2.5e16 stale Silo shares (NAV
+9.5%) → redeem ~41.5M shares at the inflated price. A donate-first ordering reaches
**$1,604,999**; 4,631 candidate executions succeed.

The ~$1.6M is the amount extractable from **this one vault at this block**, bounded by the
vault's *withdrawable* (liquid) assets — `redeem` can only be paid from liquid arks, so an
oversized redeem reverts. The historical $6.04M spanned both the lower- and higher-risk USDC
vaults; the mechanism and profit-per-vault match.

## Note on the "donated" Silo shares

The attacker pre-accumulated the impaired Silo shares over ~3 months across many wallets, buying
them cheap (real value ≈ 0) while they stayed stale-high on-chain. The benchmark funds the
attacker with them as pre-held capital and prices them at 0 (they are given up in the donation
and never recovered), so profit is measured purely in USDC — the honest attacker gain.
