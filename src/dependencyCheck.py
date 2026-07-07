import copy
import sys
import os
import subprocess
import re
from web3 import Web3

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))
sys.path.append(os.path.dirname(os.path.dirname(SCRIPT_DIR)))
dir_path = os.path.dirname(os.path.realpath(__file__))
project_path = os.path.dirname(dir_path)


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

    # open the same file in write mode and write the modified content
    with open(path, 'w') as file:
        file.write(new_content)

    output = subprocess.run(command, capture_output=True,
                            shell=True, cwd=project_path + "/src/foundryModule/")

    message = str(output.stdout)
    separator = ": =================== Separator =================="
    messages = message.split(separator)

    # only needd messages[1], messages[3], messages[5], messages[7], ...
    messages = messages[1::2]
    # print(len(messages))

    countr = 0
    for message in messages:
        # print(message)
        # print("\n=====================================================\n")
        start = "x1b[0m::\\x1b[32m"
        end = "\\x1b[0m("

        startPos = message.find(start)

        endPos = message[startPos:].find(end) + startPos

        # find funcName between first start and first end
        funcName = message[startPos + len(start):  endPos]

        if overideFuncName != None:
            funcName = overideFuncName[countr]
            countr += 1

        thisAction = Action(funcName)

        # print(funcName)
        # find related addresses
        # find all locations of "] \x1b[32m0x"

        # print(message)
        start = "x1b\[32m0x"
        res = [i.start() for i in re.finditer(start, message)]

        for r in res:
            address = message[r + len(start) - 3: r + len(start) + 39]
            if Web3.is_address(address):
                # print(address)
                if address not in thisAction.relatedAddresses:
                    thisAction.relatedAddresses.append(address)
        outputActions.append(thisAction)
        # print("\n ========================= \n")
        # 0xEb91861f8A4e1C12333F42DCE8fB0Ecdc28dA716
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

        if "=================== Separator ==================" in line:
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

    output = subprocess.run(command, capture_output=True,
                            shell=True, cwd=project_path + "/src/foundryModule/")

    message = str(output.stdout)
    separator = ": =================== Separator =================="
    messages = message.split(separator)

    # only needd messages[1], messages[3], messages[5], messages[7], ...
    messages = messages[1::2]
    # print(len(messages))

    assert len(messages) == len(ActionLists)

    ActionListsIndex = 0

    for ii in range(len(messages)):

        message = messages[ii]
        # print(message)
        lines = message.split("\\n")
        for ii in range(len(lines)):
            line = lines[ii]
            if "34maccesses" in line:
                address = hasAddress(
                    line, ActionLists[ActionListsIndex].relatedAddresses)
                if address == None:
                    sys.exit("dependencyCheck Error: address not found")
                line = lines[ii + 1]
                if "[], []" in line:
                    ActionLists[ActionListsIndex].addReadAccess(address, [])
                    ActionLists[ActionListsIndex].addWriteAccess(address, [])
                    continue
                # line is a string like "[addressA, addressB, addressC], [addressD, addressE, addressF]"
                # return [addressA, addressB, addressC], [addressD, addressE, addressF]

                readList = line[line.find("0m[") + 3: line.find("], ")]
                writeList = line[line.find(", [", line.find("], ")) + 1:]

                # print("readList: ", readList)
                # print("writeList: ", writeList)

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
