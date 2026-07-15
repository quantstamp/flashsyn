# Modeling NFT-internal vault debt in FlashSyn — the debt-shim pattern

A reusable technique, demonstrated on a Fluid (Instadapp) **T1 vault** (normal collateral +
normal debt, wstETH/USDC `0x1982CC…dcc3`): how to make FlashSyn score **borrow-side / leverage
attacks** soundly when the vault debt is not a fungible ERC20 — **with no engine change**.

Chain: Ethereum mainnet, fork block **25500000**. The attacker opens one position in `setUp()`
(100 wstETH collateral + 50,000 USDC debt) and the actions borrow / repay against it.

## The problem: vault debt is invisible to a balance-delta profit model

FlashSyn scores profit as `Σ (final − initial) × price` over fungible token balances. Fluid
vault debt is **NFT-internal and non-fungible** — there is no debt ERC20 whose `balanceOf` goes
up when you borrow. So a naive `vault_borrow_USDC` action makes the attacker's USDC balance rise
and looks like pure profit, while the **liability that came with it is invisible**. Any borrow
would register as a false positive of up to the full borrow amount.

(Framing note: this is sound for a *walk-away/default* attack — borrowed tokens you never repay
really are profit, and the on-chain health check caps the borrow at collateral value, so the EVM
itself prevents over-borrowing. It is unsound only for the *unwind/leverage* framing, where a
rational attacker would repay, so the debt is a real cost. Modeling the debt makes **both**
framings score correctly.)

## The fix: a debt shim + a negative-priced pseudo-token (no engine change)

Two facts about the engine (`src/manifest.py`) make this a pure-manifest change:

- `calcProfit` just multiplies by `price` — **a token price may be negative**.
- The profit readout and the derived collector read a token's amount via
  `<var>.balanceOf(attacker)` — so *any* contract exposing `balanceOf` can back a "token."

So we:

1. Deploy a tiny **`DebtShim`** (in `attack.t.sol`) whose `balanceOf(attacker)` returns the
   position's **live debt** — `VaultResolver.positionByNftId(nftId).borrow` (USDC, 6 dec).
2. Register a pseudo-token in the manifest: `token_info.dUSDC = ["debtShim", 6]`,
   `initial_balances.dUSDC = 50000`, and crucially **`token_prices.dUSDC = -1.0`**, with
   `dUSDC` in `profit_tokens`.
3. Give the borrow action two `collected` effects — measure the USDC received *and* the debt
   delta (via the shim):
   ```toml
   effects = [
     { token = "USDC",  op = "add", src = "collected" },
     { token = "dUSDC", op = "add", src = "collected" },
   ]
   ```

Now a borrow of X contributes `+X (USDC) + X × (−1) (dUSDC) = 0`. The received cash and the debt
cancel; profit only appears if the collateral is genuinely mispriced. Because the shim reads the
*live* debt, this also captures price-dependent debt automatically — for a smart-debt vault whose
debt is DEX shares, a manipulated DEX would move the measured `dUSDC`, exactly what the search
needs to see. (There the shim would convert shares→token via the resolver; the T1 case here reads
a plain token amount, which is why it's the clean place to prototype.)

## Two actions

| action | in → out | call |
| --- | --- | --- |
| `vault_borrow_USDC`  | → USDC (+ debt) | `operate(nft, 0, +usdc, attacker)` |
| `vault_payback_USDC` | USDC → (− debt) | `operate(nft, 0, -usdc, attacker)` |

## Run it

```sh
python3 flashsyn.py compile    fluid_t1
python3 flashsyn.py validate   fluid_t1
python3 flashsyn.py collect    fluid_t1 --fast-using-anvil
python3 flashsyn.py synthesize fluid_t1 --fast-using-anvil > run.log
```

## Result (verified end-to-end)

```
in total  253  executions succeed
Best Profit  0
```

**253 candidate sequences execute successfully** — the borrows and paybacks really do run and
move USDC — yet **every one scores exactly 0**. That is the debt model working: the negative-
priced `dUSDC` cancels the borrowed USDC precisely. **Delete `dUSDC` from `profit_tokens` and
re-run, and those same borrows would report up to +$100,000 of (fake) profit** — that contrast
is the whole point. The pattern generalizes to any NFT-position lending vault.
