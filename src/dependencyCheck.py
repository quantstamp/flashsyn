"""Storage read/write dependency analysis between protocol actions.

Runs the Foundry harness twice per action: pass 1 (executeAndParseRelevantAddresses)
scrapes the addresses each action touches; pass 2 (collectAccessInfo) inserts
vm.record()/vm.accesses() and scrapes the read/write storage slots. Two actions are
dependent when one reads a slot the other writes.

Modernised for forge >= 1.x. The 2021-era code scraped ANSI-coloured `-vvv` text; a
piped modern forge emits no colour, so this parses the plain decoded `-vvvv` trace
instead. The load-bearing details (all learned the hard way against forge 1.7.1) are
commented inline: the trace-form `SEPARATOR`, the EIP-55 checksum address filter, and
the `-vvvv` requirement in `_run_forge`.
"""
import copy
import sys
import os
import subprocess
import re
from web3 import Web3

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
sys.path.append(os.path.dirname(SCRIPT_DIR))
sys.path.append(os.path.dirname(os.path.dirname(SCRIPT_DIR)))
dir_path = os.path.dirname(os.path.realpath(__file__))
project_path = os.path.dirname(dir_path)

from conventions import SEPARATOR_TEXT


class Action():
    def __init__(self, funcName):
        self.funcName = funcName
        self.relatedAddresses = []
        self.readMap = {}
        self.writeMap = {}

    def accessesString(self):
        returnStr = ""
        for address in self.relatedAddresses:
            returnStr += "        vm.accesses(address({}));\n".format(address)
        return returnStr

    def addReadAccess(self, address, storages):
        if address not in self.readMap:
            self.readMap[address] = []
        for storage in storages:
            if storage not in self.readMap[address]:
                self.readMap[address].append(storage)

    def addWriteAccess(self, address, storages):
        if address not in self.writeMap:
            self.writeMap[address] = []
        for storage in storages:
            if storage not in self.writeMap[address]:
                self.writeMap[address].append(storage)


def hasAddress(string, addresses):
    for address in addresses:
        if address in string:
            return address
    return None


# How the separator (conventions.SEPARATOR_TEXT) renders in modern forge (>=1.x)
# `-vvvv` traces. Piped output carries no ANSI color, so we match the decoded text.
# The separator is emitted from the test as `emit log("<SEPARATOR_TEXT>")` and shows
# up in the Traces block as `emit log(val: "<SEPARATOR_TEXT>")`. Appending `")` to the
# split key restricts matches to that trace form: the plain Logs-block echo of the
# same line has no closing `")`, so we don't double-count it.
SEPARATOR = SEPARATOR_TEXT + '")'
ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*m')


def _decode(stdout: bytes) -> str:
    text = stdout.decode("utf-8", errors="replace") if isinstance(stdout, (bytes, bytearray)) else stdout
    return ANSI_ESCAPE.sub("", text)


def _run_forge(command: str) -> str:
    """Run a forge command under foundryModule at full trace verbosity.

    dependencyCheck needs `-vvvv` so the traces include the action calls and the
    `vm.accesses` staticcall return values; append it if the caller didn't.
    """
    if "-vvvv" not in command:
        command = command + " -vvvv"
    output = subprocess.run(command, capture_output=True,
                            shell=True, cwd=project_path + "/src/foundryModule/")
    return _decode(output.stdout)


# def parseExecutionTrace(trace, address, functionName)::


def executeAndParseRelevantAddresses(command: str, overideFuncName=None):
    # execute command under src/foundryModule
    # parse the output
    # get a list of relevant addresses
    outputActions = []

    # remove all vm.accesses and record()
    path = project_path + "/src/foundryModule/src/test/attack.t.sol"
    with open(path, "r") as file:
        lines = file.readlines()
    new_lines = []
    for line in lines:
        if "vm.accesses" not in line and "vm.record" not in line:
            new_lines.append(line)
    new_content = "".join(new_lines)
    with open(path, 'w') as file:
        file.write(new_content)


    message = _run_forge(command)
    messages = message.split(SEPARATOR)

    # each action is wrapped by a pair of separators, so the action bodies are the
    # odd-indexed segments (messages[1], messages[3], ...).
    messages = messages[1::2]

    countr = 0
    for message in messages:
        # first `::funcName(` in the section is the section's top-level call, e.g.
        # a trace line `[22492] Vault::poke(42)`. NOTE: this is only a human-facing
        # label for the printed dependency report; the actual dependency analysis
        # uses the storage read/write maps below, never funcName. It can therefore
        # be a cheatcode: an action whose first line is `vm.stopPrank()` (e.g.
        # euler's liquidate) is labelled "stopPrank". vm.record/vm.accesses are
        # stripped above before this pass, so they never win the match.
        m = re.search(r'::(\w+)\(', message)
        funcName = m.group(1) if m else ""

        if overideFuncName != None:
            funcName = overideFuncName[countr]
            countr += 1

        thisAction = Action(funcName)

        # forge prints decoded addresses in EIP-55 checksummed (mixed-case) form,
        # whereas raw hex data (calldata / storage words) is lowercase. Requiring a
        # valid checksum keeps genuine addresses and rejects lowercase 40-hex data.
        # The lookarounds stop the match from grabbing a 40-char prefix of a longer
        # (e.g. 64-hex) word. These addresses get inlined into Solidity as address
        # literals, so they must be checksummed or solc rejects them.
        for m in re.finditer(r'(?<![0-9a-fA-F])0x[0-9a-fA-F]{40}(?![0-9a-fA-F])', message):
            address = m.group(0)
            if Web3.is_checksum_address(address) and address not in thisAction.relatedAddresses:
                thisAction.relatedAddresses.append(address)
        outputActions.append(thisAction)
    return outputActions


def modifyAttackTestFile(ActionLists):
    # read content and intert new lines

    newlines = []
    lines = None
    with open(project_path + "/src/foundryModule/src/test/attack.t.sol", "r") as f:
        lines = f.readlines()

    # count number of vm.accesses
    counter = 0
    for line in lines:
        if "vm.accesses" in line:
            counter += 1
    if counter >= len(ActionLists):
        return

    ActionListIndex = 0

    counter = 0
    for line in lines:

        if line == None:
            continue

        if SEPARATOR_TEXT in line:
            counter += 1
            if counter % 2 == 1:
                newlines.append(line)
                newlines.append("        vm.record();\n")
            else:
                newlines.append(ActionLists[ActionListIndex].accessesString())
                newlines.append(line)
                ActionListIndex += 1
        else:
            newlines.append(line)

    with open(project_path + "/src/foundryModule/src/test/attack.t.sol", "w") as f:
        f.writelines(newlines)


def getStorage(string: str) -> list:
    # separator is , or ] or [ or space or \n
    # return a list of storage
    # string is like " [0x0000000000000000000000000000000000000000000000000000000000000000, 0x1c125f7eba8fbca5a7c3b009aee58c491bd0dbfad8a4957e31c7af6a8621c71c]"
    # return 0x0000000000000000000000000000000000000000000000000000000000000000, 0x1c125f7eba8fbca5a7c3b009aee58c491bd0dbfad8a4957e31c7af6a8621c71c

    storages = []
    string = string.replace("[", "")
    string = string.replace("]", "")
    string = string.replace(" ", "")
    string = string.replace("\n", "")
    string = string.replace(",", "")
    string = string.replace(".", "")

    separator = "0x"
    res = [i.start() for i in re.finditer(separator, string)]
    for r in res:
        storage = string[r: r + 66]
        storages.append(storage)

    # check if storages are valid
    # except for first two digits, other digits should be 0-9 or a-f
    for storage in storages:
        for ii in range(2, len(storage)):
            if not storage[ii].isalnum():
                sys.exit(
                    "dependencyCheck Error: storage {} is not valid".format(storage[ii]))
    return storages


def collectAccessInfo(command, ActionLists):
    path = project_path + "/src/foundryModule/src/test/attack.t.sol"
    with open(path, "r") as file:
        content = file.read()
    # replace the old string with the new string
    new_content = content.replace('address(uint160(uint256(keccak256(abi.encodePacked("FakeAttacker")))))',
                                  'address(uint160(uint256(keccak256(abi.encodePacked("attacker")))))')
    new_content = new_content.replace('address(uint160(uint256(keccak256(abi.encodePacked("FakeAttacker2")))))',
                                      'address(uint160(uint256(keccak256(abi.encodePacked("attacker2")))))')
    new_content = new_content.replace('address(uint160(uint256(keccak256(abi.encodePacked("FakeAttacker3")))))',
                                      'address(uint160(uint256(keccak256(abi.encodePacked("attacker3")))))')

    # open the same file in write mode and write the modified content
    with open(path, 'w') as file:
        file.write(new_content)

    ActionList1 = collectAccessInfoOnce(command, copy.deepcopy(ActionLists))
    # open the file in read mode and read its content

    with open(path, "r") as file:
        content = file.read()

    # replace the old string with the new string
    new_content = content.replace('address(uint160(uint256(keccak256(abi.encodePacked("attacker")))))',
                                  'address(uint160(uint256(keccak256(abi.encodePacked("FakeAttacker")))))')
    new_content = new_content.replace('address(uint160(uint256(keccak256(abi.encodePacked("attacker2")))))',
                                      'address(uint160(uint256(keccak256(abi.encodePacked("FakeAttacker2")))))')
    new_content = new_content.replace('address(uint160(uint256(keccak256(abi.encodePacked("attacker3")))))',
                                      'address(uint160(uint256(keccak256(abi.encodePacked("FakeAttacker3")))))')

    # open the same file in write mode and write the modified content
    with open(path, 'w') as file:
        file.write(new_content)

    ActionList2 = collectAccessInfoOnce(command, copy.deepcopy(ActionLists))

    if len(ActionList1) != len(ActionList2):
        sys.exit(
            "dependencyCheck Error: ActionList1 and ActionList2 have different length")

    for ii in range(len(ActionList1)):
        for relatedAddress in ActionList1[ii].relatedAddresses:
            if relatedAddress not in ActionList2[ii].relatedAddresses:
                sys.exit(
                    "dependencyCheck Error: ActionList1 relatedAddresses and ActionList2 relatedAddresses are different")
        for relatedAddress in ActionList2[ii].relatedAddresses:
            if relatedAddress not in ActionList1[ii].relatedAddresses:
                sys.exit(
                    "dependencyCheck Error: ActionList1 relatedAddresses and ActionList2 relatedAddresses are different")

        for relatedAddress in ActionList1[ii].relatedAddresses:
            temp = []
            for storage in ActionList1[ii].readMap[relatedAddress]:
                if storage in ActionList2[ii].readMap[relatedAddress]:
                    temp.append(storage)
            ActionLists[ii].readMap[relatedAddress] = temp
            temp = []
            for storage in ActionList1[ii].writeMap[relatedAddress]:
                if storage in ActionList2[ii].writeMap[relatedAddress]:
                    temp.append(storage)
            ActionLists[ii].writeMap[relatedAddress] = temp

    return ActionLists


def collectAccessInfoOnce(command, ActionLists):

    message = _run_forge(command)
    messages = message.split(SEPARATOR)

    # only need the action bodies (odd-indexed segments), same as the first pass.
    messages = messages[1::2]

    if len(messages) != len(ActionLists):
        sys.exit("dependencyCheck Error: parsed {} action sections but expected {} "
                 "(forge trace format mismatch?)".format(len(messages), len(ActionLists)))

    ActionListsIndex = 0

    for ii in range(len(messages)):

        message = messages[ii]
        lines = message.split("\n")
        for ii in range(len(lines)):
            line = lines[ii]
            # a vm.accesses cheatcode call renders as `VM::accesses(<addr>) [staticcall]`
            # with the storage result on the following `← [Return] [reads], [writes]` line.
            if "VM::accesses(" in line:
                address = hasAddress(
                    line, ActionLists[ActionListsIndex].relatedAddresses)
                if address == None:
                    sys.exit("dependencyCheck Error: address not found")
                line = lines[ii + 1]
                # capture the two bracketed lists after `[Return]`
                m = re.search(r'\[Return\]\s*(\[.*?\]),\s*(\[.*?\])', line)
                if m is None:
                    ActionLists[ActionListsIndex].addReadAccess(address, [])
                    ActionLists[ActionListsIndex].addWriteAccess(address, [])
                    continue
                readList = m.group(1)
                writeList = m.group(2)

                readstorages = getStorage(readList)
                ActionLists[ActionListsIndex].addReadAccess(
                    address, readstorages)
                # print(readstorages)

                writestorages = getStorage(writeList)
                ActionLists[ActionListsIndex].addWriteAccess(
                    address, writestorages)
                # print(writestorages)

                # check if writestorages is a subset of readstorages
                for storage in writestorages:
                    if storage not in readstorages:
                        sys.exit(
                            "dependencyCheck Error: write storage {} is not in read storage".format(storage))

                ii += 1

        ActionListsIndex += 1

    return ActionLists


def findReadWriteDependency(ActionList, verbose=False):
    Dependencies = []
    for ii in range(0, len(ActionList)):
        Dependencies.append([])
        for jj in range(0, len(ActionList)):
            if ii == jj:
                continue
            keyAddresses = []
            for address in ActionList[ii].relatedAddresses:
                if address in ActionList[jj].relatedAddresses:
                    for storage in ActionList[ii].readMap[address]:
                        if storage in ActionList[jj].writeMap[address]:

                            if address not in keyAddresses:
                                keyAddresses.append(address)

            if len(keyAddresses) != 0:
                Dependencies[ii].append((ActionList[jj], keyAddresses))

    for ii in range(len(Dependencies)):
        if len(Dependencies[ii]) == 0:
            print("Action {} has no dependency".format(
                ActionList[ii].funcName))
        else:
            print("Action {} has {} relevant actions: ".format(
                ActionList[ii].funcName, len(Dependencies[ii])), end="")
            for jj in range(len(Dependencies[ii])):
                print(Dependencies[ii][jj][0].funcName, end=" ")
            print("")

        if verbose:
            for jj in range(len(Dependencies[ii])):
                print("Action {} depends on Action {}".format(
                    ActionList[ii].funcName, Dependencies[ii][jj][0].funcName))
                print("key addresses: {}".format(Dependencies[ii][jj][1]))
                print("")


if __name__ == "__main__":

    # Pass the full forge run command as a single argument, e.g.:
    #   python3 src/dependencyCheck.py "./run.sh euler ETH 16818064 -vvv"
    if len(sys.argv) < 2:
        sys.exit("Usage: python3 dependencyCheck.py \"<run command>\"\n"
                 "  e.g. python3 dependencyCheck.py \"./run.sh euler ETH 16818064 -vvv\"")
    command = sys.argv[1]
    overrideFuncNames = []

    outputActions = executeAndParseRelevantAddresses(command)
    modifyAttackTestFile(outputActions)
    ActionList = collectAccessInfo(command, outputActions)
    findReadWriteDependency(ActionList)
