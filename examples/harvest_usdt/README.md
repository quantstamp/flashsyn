# Harvest Finance (fUSDC) example

The [Harvest Finance](https://etherscan.io/tx/0x35f8d2f572fceaac9288e5d462117850ef2694786992a8c3f6d02612277b0877)
exploit (26 Oct 2020), fUSDC leg, as a worked FlashSyn analysis. This is a second
reference (alongside `examples/euler/`) for filling in the templates in `src/`.

The fUSDC vault priced its underlying by reading the Curve y-pool. The attacker
depresses USDC inside the pool, deposits the now-cheap USDC into the vault (minting
too many shares), restores the pool, and redeems the shares for more USDC than it
started with.

- `Harvest_USDTActions.py` — the filled-in Python action model (counterpart to `src/FlashSynProActions/template.py`).
- `attack.t.sol` — the filled-in Foundry harness (counterpart to `src/foundryModule/src/test/template.t.sol`).

Chain: Ethereum mainnet, fork block **11129474**. Initial capital:
18,308,555.417594 USDT + 50,000,000 USDC (the amounts the historical attack
flash-loaned).

## Four actions

| action | in → out |
| --- | --- |
| `Curve_USDT2USDC` | USDT → USDC (Curve `exchange_underlying(2,1,·)`) |
| `Curve_USDC2USDT` | USDC → USDT (Curve `exchange_underlying(1,2,·)`) |
| `fUSDC_deposit`   | USDC → fUSDC shares |
| `fUSDC_withdraw`  | fUSDC shares → USDC |

## Run it

Place the two files where the engine expects them, then run **everything from the
repo root** — the engine loads `settings.toml` relative to the working directory:

```sh
cp examples/harvest_usdt/Harvest_USDTActions.py src/FlashSynProActions/
cp examples/harvest_usdt/attack.t.sol           src/foundryModule/src/test/attack.t.sol
mkdir -p initialDataPoints/harvest_usdt

# 1. compile (this one runs inside foundryModule)
( cd src/foundryModule && ./run.sh Harvest_USDT ETH 11129474 )

# 2. action dependencies
python3 src/dependencyCheck.py "./run.sh Harvest_USDT ETH 11129474"

# 3. collect data points (runs initialPass)
python3 src/FlashSynProActions/Harvest_USDTActions.py

# 4. in Harvest_USDTActions.py main(): comment out `ActionWrapper.initialPass(...)`
#    and uncomment the Synthesizer block

# 5. synthesize
python3 src/FlashSynProActions/Harvest_USDTActions.py > HarvestUSDTLog.txt
```

Expected result: FlashSyn rediscovers the exploit — best vector
`Curve_USDT2USDC → fUSDC_deposit → Curve_USDC2USDT → fUSDC_withdraw`, with a
combined USDT+USDC profit on the order of ~300K (the historical attack netted
≈307,418). Early rounds printing `0 executions succeed` / `Best Profit 0.2` are
the pre-refinement phase, not a failure — let it run to `End of Synthesis`.

## Notes on the port

Ported from the original `research-flashsyn` benchmark (`src/Actions/Harvest_USDT.py`),
which used the deprecated attack-contract + real-flash-loan execution mode. This
version uses the modern DVD/EOA style (like Euler): the attacker is a pranked EOA
pre-funded with the loan amounts in `setUp()`.

- **USDC** is minted through the real `masterMinter` (the path the Euler example
  already verifies).
- **USDT** has no mint hook, so `setUp()` writes its balance storage slot directly
  (`balances` mapping = slot 2) and `require`s the write took, so a wrong slot fails
  loud rather than silently funding 0.

> **Verified end-to-end (2026-07-09).** Full fork synthesis in the `flashsyn:modern`
> Docker image against a mainnet archive fork at block 11129474 (forge 1.7.1, Python
> 3.12 + vendored shgo). Data collection: 1,931 points / 65 pkl files (~135s).
> Synthesis (maxSynthesisLen=4, Pruning + CounterExampleLoop) rediscovers the exploit:
> **`Curve_USDT2USDC → fUSDC_deposit → Curve_USDC2USDT → fUSDC_withdraw`**, params
> `[17089774, 17624463, 15666845, 18223614]`, **estimated profit 65,296 ≈ actual
> on-chain profit 66,764** (72 concrete executions succeeded). The vector matches the
> historical attack; the validated profit is smaller than the historical ~307K because
> the optimizer settled on ~17M-scale trades rather than the attacker's ~50M.
