# Harvest Finance (fUSDT) example

The Harvest Finance exploit (26 Oct 2020), fUSDT leg — the sibling of the fUSDC
attack in `examples/harvest_usdt/`, run minutes later against the fUSDT vault.

Same mechanism, mirrored tokens: the fUSDT vault priced its underlying by reading
the Curve y-pool. The attacker depresses USDT inside the pool, deposits the
now-cheap USDT into the vault (minting too many shares), restores the pool, and
redeems the shares for more USDT than it started with.

- `manifest.toml` — the declarative benchmark (the CLI builds the action model from it).
- `attack.t.sol` — the filled-in Foundry harness.

Chain: Ethereum mainnet, fork block **11129500**. Initial capital:
20,000,000 USDC + 50,000,000 USDT.

> Naming note: the benchmark is called "Harvest_USDC" (matching the original
> `research-flashsyn` benchmark name), but the vault it drains is **fUSDT** — the
> label refers to the leg, not the deposited token.

## Four actions

| action | in → out |
| --- | --- |
| `Curve_USDC2USDT` | USDC → USDT (Curve `exchange_underlying(1,2,·)`) |
| `Curve_USDT2USDC` | USDT → USDC (Curve `exchange_underlying(2,1,·)`) |
| `fUSDT_deposit`   | USDT → fUSDT shares |
| `fUSDT_withdraw`  | fUSDT shares → USDT |

## Run it

From the repo root:

```sh
python3 flashsyn.py compile    harvest_usdc   # compile the harness against the fork
python3 flashsyn.py collect    harvest_usdc   # collect the initial data points (~2 min)
python3 flashsyn.py synthesize harvest_usdc   # run the synthesis (~2 min)
```

The CLI loads `examples/harvest_usdc/` in place — no copying files into the engine
and no editing source to switch between collection and synthesis.

Expected result: FlashSyn rediscovers the exploit — best vector
`Curve_USDC2USDT → fUSDT_deposit → Curve_USDT2USDC → fUSDT_withdraw`, with a
combined USDT+USDC profit on the order of ~330K (the historical attack netted
≈338,545: ~319,524 USDT + ~19,021 USDC).

## Notes on the port

Ported from the original `research-flashsyn` benchmark (`src/Actions/Harvest_USDC.py`).
Same modernization as the fUSDC example: modern DVD/EOA style, USDC minted via the
real `masterMinter`, USDT funded by a direct balance-slot write (slot 2) with a
`require` assertion. See `examples/harvest_usdt/README.md` for the full rationale.

> **Verified end-to-end (2026-07-09).** Full fork synthesis in the `flashsyn:modern`
> Docker image against a mainnet archive fork at block 11129500 (forge 1.7.1, Python
> 3.12 + vendored shgo). Data collection: 1,637 points / 65 pkl files (~134s).
> Synthesis (maxSynthesisLen=4, Pruning + CounterExampleLoop) rediscovers the exploit:
> **`Curve_USDC2USDT → fUSDT_deposit → Curve_USDT2USDC → fUSDT_withdraw`**, params
> `[8240307, 46354980, 7363174, 47955515]`, **estimated profit 104,699 ≈ actual
> on-chain profit 100,111** (1001 concrete executions succeeded). Here the optimizer
> found ~46M-scale trades, close to the attacker's ~50M; validated profit is ~100K vs
> the historical ~338K.
