#!/usr/bin/env python3
"""flashsyn — run a FlashSyn example without copying files or editing source.

Usage (from the repo root):
    python3 flashsyn.py compile    <example> [--fast-using-anvil]
    python3 flashsyn.py validate   <example> [--fast-using-anvil]   # smoke each action from the manifest
    python3 flashsyn.py deps       <example> [--fast-using-anvil]
    python3 flashsyn.py collect    <example> [--fast-using-anvil]
    python3 flashsyn.py synthesize <example> [--fast-using-anvil] [--jobs N]

<example> is a directory under examples/ (e.g. harvest_usdt). It must hold a
manifest.toml (the declarative action model) and one attack.t.sol. The CLI places
the harness where forge expects it and drives collect-vs-synthesize by subcommand,
replacing the old "cp two files, then comment-toggle main()" flow.

--jobs N parallelises `synthesize` across N processes (default 1): each round's
candidate traces have their shgo optimisation run concurrently. Before the
AttackDAG.setSimplifierExpander memoisation this was negligible (~2% even at jobs=8)
because redundant DAG matching dominated the runtime; with that removed it gives a modest
real gain — Euler: jobs=2 is 130s->104s (~1.25x), plateauing by jobs=4 and regressing at
jobs=8 (only ~7 traces/round, so extra workers just add fork/IPC overhead). Sweet spot
~2-4; it scales with search breadth (traces per round), not with N. (`collect` is
unaffected: it's forge-bound — use --fast-using-anvil.)

--fast-using-anvil starts ONE local anvil fork of the example's chain/block for the whole command
and points forge at it. `collect` fires forge ~200 times and each fresh forge process
re-establishes its fork over the RPC (several sequential round-trips at network
latency); a persistent local anvil collapses those to localhost — measured ~3.4x
faster on the Euler collect (248s -> 72s, identical data). Needs `anvil` on PATH (ships
with Foundry) and the chain's real endpoint to fork from (an env override such as
`ETH=<rpc>` wins, else run.sh's baked-in default).
"""
import os
import re
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
FOUNDRY = os.path.join(ROOT, "src", "foundryModule")
HARNESS_DEST = os.path.join(FOUNDRY, "src", "test", "attack.t.sol")

# The engine imports its packages by bare name (from Actions... / from synthesizer
# ...). Replicate the path an action model got when run from src/FlashSynProActions:
# the src/ dir plus the repo root, nothing more.
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))


def _load_example(name):
    """Place the example's harness where forge expects it; return its setup dict.

    Every example is declarative: a manifest.toml (the action model) plus its
    Solidity harness attack.t.sol (setUp / interfaces / profitSummary), which is
    copied to where forge and the collector generator look.
    """
    exdir = os.path.join(ROOT, "examples", name)
    if not os.path.isdir(exdir):
        sys.exit("no example directory: examples/{}".format(name))
    harness = os.path.join(exdir, "attack.t.sol")
    if not os.path.isfile(harness):
        sys.exit("missing examples/{}/attack.t.sol".format(name))
    os.makedirs(os.path.dirname(HARNESS_DEST), exist_ok=True)
    with open(harness) as src, open(HARNESS_DEST, "w") as dst:
        dst.write(src.read())

    manifest = os.path.join(exdir, "manifest.toml")
    if not os.path.isfile(manifest):
        sys.exit("missing examples/{}/manifest.toml".format(name))
    import manifest as manifest_loader
    return manifest_loader.load(manifest)


def _rpc_for_chain(chain):
    """The real endpoint anvil forks from: an env override wins, else run.sh's default.

    Kept DRY with run.sh (which resolves `<CHAIN>="${<CHAIN>:-<default>}"`) so --fast-using-anvil
    forks from exactly what a plain run would have hit.
    """
    if os.environ.get(chain):
        return os.environ[chain]
    pat = re.compile(r'^\s*' + re.escape(chain) + r'="\$\{' + re.escape(chain) + r':-([^"]+)\}"')
    with open(os.path.join(FOUNDRY, "run.sh")) as f:
        for line in f:
            m = pat.match(line)
            if m:
                return m.group(1)
    sys.exit("--fast-using-anvil: no endpoint to fork {} from; set {}=<rpc> or add a run.sh default".format(chain, chain))


def _start_anvil(rpc, block, port=8545):
    """Start a background anvil fork; return (proc, url) once it answers JSON-RPC."""
    try:
        proc = subprocess.Popen(
            ["anvil", "--fork-url", rpc, "--fork-block-number", str(block), "--port", str(port), "--silent"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        sys.exit("--fast-using-anvil: 'anvil' not found on PATH (it ships with Foundry: run foundryup)")
    url = "http://127.0.0.1:{}".format(port)
    body = b'{"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}'
    for _ in range(120):
        if proc.poll() is not None:
            sys.exit("--fast-using-anvil: anvil exited before becoming ready (is the fork RPC reachable?)")
        try:
            req = urllib.request.Request(url, data=body, headers={"content-type": "application/json"})
            if urllib.request.urlopen(req, timeout=2).read():
                return proc, url
        except Exception:
            time.sleep(1)
    proc.terminate()
    sys.exit("--fast-using-anvil: anvil did not become ready in time")


def _parse_args(args):
    """Pull flags out of the arg list, returning (cmd, name, use_anvil, jobs).

    Flags: --fast-using-anvil (bool) and --jobs N / --jobs=N (int, clamped to 1..cpus).
    """
    use_anvil = "--fast-using-anvil" in args
    jobs = "1"
    positional = []
    it = iter(a for a in args if a != "--fast-using-anvil")
    for a in it:
        if a == "--jobs":
            jobs = next(it, "1")
        elif a.startswith("--jobs="):
            jobs = a.split("=", 1)[1]
        else:
            positional.append(a)
    try:
        jobs = max(1, min(int(jobs), os.cpu_count() or 1))
    except ValueError:
        sys.exit("--jobs takes an integer")
    if len(positional) != 2 or positional[0] not in ("compile", "validate", "deps", "collect", "synthesize"):
        sys.exit(__doc__)
    return positional[0], positional[1], use_anvil, jobs


def main():
    cmd, name, use_anvil, jobs = _parse_args(sys.argv[1:])
    os.chdir(ROOT)  # settings.toml + run.sh resolve relative to the repo root

    setup = _load_example(name)
    import config
    config.processNum = jobs  # synthesize parallelises its per-trace shgo across this many

    anvil_proc = None
    if use_anvil:
        # config.command is "./run.sh <contract> <chain> <block>" (set by the example).
        parts = config.command.split()
        chain, block = parts[2], parts[3]
        rpc = _rpc_for_chain(chain)          # the REAL endpoint anvil forks FROM
        anvil_proc, anvil_url = _start_anvil(rpc, block)
        # run.sh points forge at ${FORK_URL:-$RPC}; setting FORK_URL routes every forge
        # invocation (compile/deps/collect/synthesize) through the local fork, while the
        # chain var (ETH/BSC/...) keeps meaning the real endpoint anvil forked from.
        os.environ["FORK_URL"] = anvil_url
        print("[anvil] forking {} @ block {} -> {}".format(chain, block, anvil_url))

    try:
        if cmd == "compile":
            subprocess.run(config.command + " -vv", shell=True, cwd=FOUNDRY)
        elif cmd == "validate":
            # Generate a per-action smoke harness from the manifest (no hand-written tests)
            # and run it: does each action execute from a token-flow prestate? See src/probe.py.
            import probe
            from conventions import extract_preamble
            with open(HARNESS_DEST) as f:
                preamble = extract_preamble(f.read())
            harness, idx = probe.build_validate_harness(
                preamble, setup["actions"], setup["wrapper"].initialBalances)
            with open(HARNESS_DEST, "w") as f:
                f.write(harness)
            command = config.command if "--json" in config.command else config.command + " --json"
            out = subprocess.run(command, shell=True, cwd=FOUNDRY, capture_output=True)
            probe.report(out.stdout, idx)
        elif cmd == "deps":
            subprocess.run([sys.executable, os.path.join(ROOT, "src", "dependencyCheck.py"), config.command])
        elif cmd == "collect":
            w = setup["wrapper"]
            w.initialPass(setup["actions"], setup["dependencies"], w)
        elif cmd == "synthesize":
            from synthesizer import Synthesizer
            w = setup["wrapper"]
            w.runinitialPass()
            Synthesizer(setup["actions"], w, config.processNum).synthesis(setup["max_len"], True, True)
    finally:
        if anvil_proc is not None:
            anvil_proc.terminate()
            try:
                anvil_proc.wait(timeout=10)
            except Exception:
                anvil_proc.kill()


if __name__ == "__main__":
    main()
