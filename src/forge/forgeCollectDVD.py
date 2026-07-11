import subprocess
import os, sys
import config
from forge.forgeJson import parse_datapoints

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))
sys.path.append(os.path.dirname(os.path.dirname(SCRIPT_DIR)))


import Actions.Adapter
from Actions.macros import DVD
from conventions import extract_preamble

dir_path = os.path.dirname(os.path.realpath(__file__))
project_path = os.path.dirname(dir_path)
project_path = os.path.dirname(project_path)

HARNESS_PATH = project_path + "/src/foundryModule/src/test/attack.t.sol"


def _preamble_for(ActionWrapper):
    """The harness preamble for this benchmark, cached on the ActionWrapper class.

    Prefer an explicit start_str literal if the action model provides one (Euler
    still does). Otherwise read it from the authored attack.t.sol so the preamble
    lives in exactly one place. The first ForgeDataCollectorDVD is always
    built before the harness is first overwritten, and extract_preamble slices the
    same preamble out of a generated file too, so this is safe to read at any point.
    """
    explicit = getattr(ActionWrapper, "start_str", "")
    if explicit and explicit.strip():
        return explicit
    cached = ActionWrapper.__dict__.get("_loaded_preamble")
    if cached is not None:
        return cached
    try:
        with open(HARNESS_PATH) as f:
            preamble = extract_preamble(f.read())
    except FileNotFoundError:
        raise FileNotFoundError(
            "no start_str set and no harness at {} to read the preamble from; "
            "copy the example's attack.t.sol into place first".format(HARNESS_PATH))
    ActionWrapper._loaded_preamble = preamble
    return preamble


class ForgeDataCollectorDVD:
    def __init__(self, ActionWrapper):

        self.ExecutionMode = DVD  # 0 for ETH  1 for BSC  2 for DVD
        # block num
        self.ActionWrapper = ActionWrapper
        self.startStr = _preamble_for(ActionWrapper)  # harness preamble (start_str or read from attack.t.sol)

        self.dataPoints = []  # parameters input ==> stats collected
        # list of list of list(size = 2)
        # example: [[[12], []], [[], []]]
        # index represents the data collector number !!!
        self.dataCollectorCount = 0
        self.attackContract = ""
        self.functionCounter = 0

        self.collectorContract = ""

        self.collectorContract2 = ""
        self.helperCount = -1
        self.isAddcollectorContract2 = False

    def initializeAttackContract(self, contract: str):
        input_strings = ["uint a", ", uint b", ", uint c", ", uint d", ", uint e",
                     ", uint f", ", uint g", ", uint h", ", uint i", ", uint j", ", uint k"]
        insert_inside_strings = ["a", "b", "c", "d",
                             "e", "f", "g", "h", "i", "j", "k"]
        
        ## replace $$ in contract with insert_inside_strings
        input_string_ptr = 0
        while "$$" in contract:
            if input_string_ptr >= len(insert_inside_strings):
                raise ValueError("attack exceeds the {}-parameter pool".format(len(insert_inside_strings)))
            contract = contract.replace('$$', insert_inside_strings[input_string_ptr], 1)
            input_string_ptr += 1

        argument_str = ""
        for i in range(input_string_ptr):
            argument_str += input_strings[i]
        self.helperCount += 1
        temp = '''
    function helper''' + str(self.helperCount) + '_(' + argument_str + ') internal {'
        temp += contract
        temp += '''}   
        '''
        
        self.collectorContract2 += temp


    def addAttackContract(self, contract: str):

        input_strings = ["uint a", ", uint b", ", uint c", ", uint d", ", uint e",
                     ", uint f", ", uint g", ", uint h", ", uint i", ", uint j", ", uint k"]
        insert_inside_strings = ["a", "b", "c", "d",
                             "e", "f", "g", "h", "i", "j", "k"]
        
        ## replace $$ in contract with insert_inside_strings
        input_string_ptr = 0
        while "$$" in contract:
            if input_string_ptr >= len(insert_inside_strings):
                raise ValueError("attack exceeds the {}-parameter pool".format(len(insert_inside_strings)))
            contract = contract.replace('$$', insert_inside_strings[input_string_ptr], 1)
            input_string_ptr += 1
        argument_str = ""
        for i in range(input_string_ptr):
            argument_str += input_strings[i]

        self.helperCount += 1
        temp = '''
            function helper''' + str(self.helperCount) + '_(' + argument_str + ') internal {'
        temp += contract
        temp += '''}   
                '''
        self.attackContract += temp
        

    def updateAttackContract(self, contract: str):
        self.dataCollectorCount = 0
        self.attackContract = contract

    def addDataCollector(self, paraList, order=None):
        if not self.isAddcollectorContract2:
            self.collectorContract += self.collectorContract2
            self.isAddcollectorContract2 = True

        temp = '''
    function testExample''' + str(self.dataCollectorCount) + '''_() public {\n'''
        temp += "       helper" + str(self.helperCount) + "_("

        for para in paraList:
            temp += str(para) + ", "
        if paraList:            # zero-param actions (numInputs=0) leave nothing to trim;
            temp = temp[:-2]    # trimming "_(" would emit a malformed "helperN);"
        temp += ");"
        temp += '''
    }
        '''
        self.collectorContract += temp
        self.dataCollectorCount += 1
        # order = the terminal action's measured-token names (approxN order), so the parser
        # can map a named "FlashSyn: tok=val ..." revert to positions regardless of emit order.
        self.dataPoints.append([paraList, None, order])
        # print(self.dataCollectorCount - 1)
        return self.dataCollectorCount - 1

    def cleanDataCollector(self):
        self.collectorContract = ""
        self.dataCollectorCount = 0

    def updateDataCollectorContract(self):

        with open(project_path + "/src/foundryModule/src/test/attack.t.sol", "w") as solFile:
            solFile.write(self.startStr + self.attackContract + self.collectorContract + "\n}")

    def executeCollectData(self):
        # print(self.ActionWrapper.__name__)
        # Make sure and attack.sol and attack.t.sol are empty
        open(project_path + "/src/foundryModule/src/attack.sol", "w").close()

        # self.dataCollectorCount = 0
        # config.command is user-supplied (see the template) and may omit --json;
        # append it so parse_datapoints gets structured output. See forge/forgeJson.py.
        command = config.command
        if "--json" not in command:
            command += " --json"

        # forge occasionally returns empty stdout on a transient fork-RPC failure
        # (rate limit / timeout on the archive node). The old code fed that empty
        # output straight to the parser, so a whole batch of data points vanished
        # silently — which is how a legitimate sequence (e.g. the single-action
        # [deposit] prefix) can end up with no data and later get pruned. Retry a
        # few times on empty stdout, and surface stderr so a *deterministic* failure
        # (a real solc/compile error) is distinguishable from a transient one.
        output = None
        for attempt in range(3):
            output = subprocess.run(command, capture_output=True,
                                    shell=True, cwd=project_path + "/src/foundryModule/")
            if output.stdout and output.stdout.strip():
                break
            sys.stderr.write(
                "forgeCollect: empty forge stdout (attempt {}/3); stderr tail: {!r}\n".format(
                    attempt + 1, (output.stderr or b"")[-400:]))

        print(command)
        print(str(output.stdout)[:150])

        return parse_datapoints(output.stdout, self.dataPoints)

        # Example: [input parameters], [output parameters]
        # [[[28000299813908753, 3412170442167358], [3917983816717, 6062616627188784794744528, 495189751117167573091345]],
        # [[27000299813908753, 3412170442167358], [3917983816717, 6162616627188784794744528, 495346173235701226433441]],
        # [[0, 0], None],
        # [[0, 3412170442167358], None]]
