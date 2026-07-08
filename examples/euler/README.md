# Euler example

The [Euler Finance](https://phalcon.xyz/tx/eth/0x465a6780145f1efe3ab52f94c006065575712d2003d83d85481f3d110ed131d9)
exploit (March 2023), as a worked FlashSyn analysis. This is the reference for filling in the templates
in `src/`.

- `EulerActions.py` — the filled-in Python action model (counterpart to `src/FlashSynProActions/template.py`).
- `attack.t.sol` — the filled-in Foundry harness (counterpart to `src/foundryModule/src/test/template.t.sol`).

Chain: Ethereum mainnet, fork block **16818064**. Initial capital: 400,000,000 USDC.

## Run it

Place the two files where the engine expects them, then run **everything from the repo root** — the
engine loads `settings.toml` relative to the working directory (importing it from `src/` fails):

```sh
cp examples/euler/EulerActions.py src/FlashSynProActions/
cp examples/euler/attack.t.sol    src/foundryModule/src/test/attack.t.sol
mkdir -p initialDataPoints/euler

# 1. compile (this one runs inside foundryModule)
( cd src/foundryModule && ./run.sh euler ETH 16818064 )

# 2. action dependencies  (dependencyCheck auto-adds -vvvv; the trailing flag is optional)
python3 src/dependencyCheck.py "./run.sh euler ETH 16818064"

# 3. collect data points (runs initialPass; ~9 min under emulation)
python3 src/FlashSynProActions/EulerActions.py

# 4. in EulerActions.py main(): comment out `ActionWrapper.initialPass(...)` and
#    uncomment the Synthesizer block (CounterExampleLoop / runinitialPass / Synthesizer.synthesis)

# 5. synthesize (~10-12 min)
python3 src/FlashSynProActions/EulerActions.py > EulerLog.txt
```

Expected result: FlashSyn rediscovers the exploit — best vector
`eulerDeposit → eulerMint → eulerDonate → eulerLiquidateWithdraw`, actual on-chain profit ~22.4M USDC,
matching the polynomial estimate almost exactly. Early rounds printing `0 executions succeed` /
`Best Profit 0.2` are the pre-refinement phase, not a failure — let it run to `End of Synthesis`.

> Notes: `EulerActions.py` already sets `config.command = "./run.sh euler ETH 16818064"` to match the
> generic runner. Step 3 must finish for **all** actions (deposit/mint/donate/burn/liquidate) before
> synthesis has enough data; the collectors tolerate the expected `e/*` protocol reverts and keep only
> the `FlashSyn:` data points.
