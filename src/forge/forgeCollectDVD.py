import subprocess
import os, sys
import config
from forge.forgeJson import parse_datapoints

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))
sys.path.append(os.path.dirname(os.path.dirname(SCRIPT_DIR)))


import Actions.Adapter
from Actions.macros import DVD

dir_path = os.path.dirname(os.path.realpath(__file__))
project_path = os.path.dirname(dir_path)
project_path = os.path.dirname(project_path)


class forgedataCollectContractDVD:
    def __init__(self, ActionWrapper):

        self.ExecutionMode = DVD  # 0 for ETH  1 for BSC  2 for DVD
        # block num
        self.ActionWrapper = ActionWrapper
        self.startStr = ActionWrapper.start_str  # start code of attack tester

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

    def addDataCollector(self, paraList):
        if not self.isAddcollectorContract2:
            self.collectorContract += self.collectorContract2
            self.isAddcollectorContract2 = True

        temp = '''
    function testExample''' + str(self.dataCollectorCount) + '''_() public {\n'''
        temp += "       helper" + str(self.helperCount) + "_("

        for para in paraList:
            temp += str(para) + ", "
        temp = temp[:-2] + ");"
        temp += '''
    }   
        '''
        self.collectorContract += temp
        self.dataCollectorCount += 1
        self.dataPoints.append([paraList, None])
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

        output = subprocess.run(command, capture_output=True,
                                shell=True, cwd=project_path + "/src/foundryModule/")

        print(command)
        print(str(output.stdout)[:150])

        return parse_datapoints(output.stdout, self.dataPoints)

        # Example: [input parameters], [output parameters]
        # [[[28000299813908753, 3412170442167358], [3917983816717, 6062616627188784794744528, 495189751117167573091345]],
        # [[27000299813908753, 3412170442167358], [3917983816717, 6162616627188784794744528, 495346173235701226433441]],
        # [[0, 0], None],
        # [[0, 3412170442167358], None]]
