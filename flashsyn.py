#!/usr/bin/env python3
"""flashsyn — run a FlashSyn example without copying files or editing source.

Usage (from the repo root):
    python3 flashsyn.py compile    <example>   # compile the harness against the fork
    python3 flashsyn.py deps       <example>   # print the action dependency graph
    python3 flashsyn.py collect    <example>   # collect the initial data points
    python3 flashsyn.py synthesize <example>   # run the counter-example synthesis

<example> is a directory under examples/ (e.g. harvest_usdt). It must hold exactly
one <Name>Actions.py exposing flashsyn_setup() and one attack.t.sol. The CLI places
the harness where forge expects it and drives collect-vs-synthesize by subcommand,
replacing the old "cp two files, then comment-toggle main()" flow.
"""
import importlib.util
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
FOUNDRY = os.path.join(ROOT, "src", "foundryModule")
HARNESS_DEST = os.path.join(FOUNDRY, "src", "test", "attack.t.sol")

# The engine imports its packages by bare name (from Actions... / from synthesizer
# ...). Replicate the path an action model got when run from src/FlashSynProActions:
# the src/ dir plus the repo root, nothing more.
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))


def _load_example(name):
    """Place the example's harness where forge expects it and import its action model."""
    exdir = os.path.join(ROOT, "examples", name)
    if not os.path.isdir(exdir):
        sys.exit("no example directory: examples/{}".format(name))
    models = [f for f in os.listdir(exdir) if f.endswith("Actions.py")]
    if len(models) != 1:
        sys.exit("expected exactly one *Actions.py in examples/{}, found {}".format(name, models))
    harness = os.path.join(exdir, "attack.t.sol")
    if not os.path.isfile(harness):
        sys.exit("missing examples/{}/attack.t.sol".format(name))

    os.makedirs(os.path.dirname(HARNESS_DEST), exist_ok=True)
    with open(harness) as src, open(HARNESS_DEST, "w") as dst:
        dst.write(src.read())

    spec = importlib.util.spec_from_file_location("flashsyn_example", os.path.join(exdir, models[0]))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "flashsyn_setup"):
        sys.exit("examples/{}/{} does not define flashsyn_setup()".format(name, models[0]))
    return mod


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("compile", "deps", "collect", "synthesize"):
        sys.exit(__doc__)
    cmd, name = sys.argv[1], sys.argv[2]
    os.chdir(ROOT)  # settings.toml + run.sh resolve relative to the repo root

    mod = _load_example(name)
    setup = mod.flashsyn_setup()
    import config

    if cmd == "compile":
        subprocess.run(config.command + " -vv", shell=True, cwd=FOUNDRY)
    elif cmd == "deps":
        subprocess.run([sys.executable, os.path.join(ROOT, "src", "dependencyCheck.py"), config.command])
    elif cmd == "collect":
        w = setup["wrapper"]
        w.initialPass(setup["actions"], setup["dependencies"], w)
    elif cmd == "synthesize":
        from synthesizer import synthesizer
        w = setup["wrapper"]
        w.runinitialPass()
        config.processNum = getattr(config, "processNum", 1) or 1
        synthesizer(setup["actions"], w, config.processNum).synthesis(setup["max_len"], True, True)


if __name__ == "__main__":
    main()
