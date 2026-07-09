# Harvest Finance (fUSDT) example

The Harvest Finance exploit (26 Oct 2020), fUSDT leg — the sibling of the fUSDC
attack in `examples/harvest_usdt/`, run minutes later against the fUSDT vault.

Same mechanism, mirrored tokens: the fUSDT vault priced its underlying by reading
the Curve y-pool. The attacker depresses USDT inside the pool, deposits the
now-cheap USDT into the vault (minting too many shares), restores the pool, and
redeems the shares for more USDT than it started with.

- `Harvest_USDCActions.py` — the filled-in Python action model.
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

Place the two files where the engine expects them, then run **everything from the
repo root**:

```sh
cp examples/harvest_usdc/Harvest_USDCActions.py src/FlashSynProActions/
cp examples/harvest_usdc/attack.t.sol           src/foundryModule/src/test/attack.t.sol
mkdir -p initialDataPoints/harvest_usdc

# 1. compile (this one runs inside foundryModule)
( cd src/foundryModule && ./run.sh Harvest_USDC ETH 11129500 )

# 2. action dependencies
python3 src/dependencyCheck.py "./run.sh Harvest_USDC ETH 11129500"

# 3. collect data points (runs initialPass)
python3 src/FlashSynProActions/Harvest_USDCActions.py

# 4. in Harvest_USDCActions.py main(): comment out `ActionWrapper.initialPass(...)`
#    and uncomment the Synthesizer block

# 5. synthesize
python3 src/FlashSynProActions/Harvest_USDCActions.py > HarvestUSDCLog.txt
```

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
