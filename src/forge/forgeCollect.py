import subprocess
import os
import config
import toml
from forge.forgeJson import parse_datapoints


dir_path = os.path.dirname(os.path.realpath(__file__))

project_path = os.path.dirname(dir_path)

project_path = os.path.dirname(project_path)


# settings.toml lives at the repo root. Resolve it from __file__ (not the cwd)
# and load it lazily, so `import`-ing the engine works from any directory — the
# old `toml.load("settings.toml")` at module top crashed unless you happened to
# run from the repo root.
_settings = None


def _load_settings():
    global _settings
    if _settings is None:
        _settings = toml.load(os.path.join(project_path, "settings.toml"))
    return _settings


class forgedataCollectContract:
    def __init__(self, attackContractName: str, initialEther: int, blockNum: int):

        self.ExecutionMode = config.ExecutionMode  # 0 for ETH  1 for BSC
        # block num
        self.blockNum = blockNum
        self.dataCollectorCount = 0
        self.functionCounter = 0
        self.testStr = ""  # data collector functions
        self.dataPoints = []  # parameters input ==> stats collected
        # list of list of list(size = 2)
        # example: [[[12], []], [[], []]]

        self.startStr = '''// SPDX-License-Identifier: AGPL-3.0-or-later
pragma solidity >0.7.0;
import "ds-test/test.sol";
import "../attack.sol";
import "../stdlib.sol";
import "../Vm.sol";
import "../CheatCodes.sol";
contract attackTester is DSTest, stdCheats {
    ''' + attackContractName + ''' attackContract;
    Vm public constant vm = Vm(HEVM_ADDRESS);
    CheatCodes cheats = CheatCodes(HEVM_ADDRESS);
'''
        self.attack_startStr = ""
        self.attack_endStr = ""
        self.attackContract = ""
        if config.contract_name == "Yearn_attack":
            self.startStr += '''    constructor() {
        startHoax(address(0x9BEF5148fD530244a14830f4984f2B76BCa0dC58), 90000000000 ether);
        attackContract = new Yearn_attack();
        cheats.stopPrank();
        IDAI DAI = IDAI(0x6B175474E89094C44Da98b954EedeAC495271d0F);
        startHoax(address(0x9759A6Ac90977b93B58547b4A71c78317f391A28));
        DAI.mint(address(attackContract), 130000000e18 );
        cheats.stopPrank(); 
        IUSDC USDC = IUSDC(0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48);
        address MasterMinter = USDC.masterMinter();
        cheats.stopPrank();
        startHoax(MasterMinter);
        USDC.configureMinter(address(0x9BEF5148fD530244a14830f4984f2B76BCa0dC58), 2**256 -1);
        cheats.stopPrank();
        startHoax(address(0x9BEF5148fD530244a14830f4984f2B76BCa0dC58));
        USDC.mint(address(attackContract), 134000000e6);
    }'''
        elif config.contract_name == "Eminence_attack":
            self.startStr += '''    constructor() {
        startHoax(address(0x9BEF5148fD530244a14830f4984f2B76BCa0dC58), 90000000000 ether);
        attackContract = new Eminence_attack();
        cheats.stopPrank();
        IDAI DAI = IDAI(0x6B175474E89094C44Da98b954EedeAC495271d0F);
        startHoax(address(0x9759A6Ac90977b93B58547b4A71c78317f391A28));
        DAI.mint(address(attackContract), 15000000 * 10 ** 18 );
        cheats.stopPrank();    
    }'''
        elif config.contract_name == "ElevenFi_attack":
            self.startStr += '''    constructor() {
        startHoax(address(0x9BEF5148fD530244a14830f4984f2B76BCa0dC58), 90000000000 ether);
        attackContract = new ElevenFi_attack();
        cheats.stopPrank();
        IBUSD BUSD = IBUSD(0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56);
        cheats.prank(0xD2f93484f2D319194cBa95C5171B18C1d8cfD6C4);
        BUSD.mint(130001e18);
        cheats.prank(0xD2f93484f2D319194cBa95C5171B18C1d8cfD6C4);
        BUSD.transfer(address(attackContract), 130001e18);
        cheats.stopPrank();
    }'''
        elif config.contract_name == "bZx1_attack":
            self.startStr += '''    constructor() {
        startHoax(address(0x9BEF5148fD530244a14830f4984f2B76BCa0dC58), 90000000000 ether);
        attackContract = new bZx1_attack{value: 4500 ether}();
        cheats.stopPrank();
        IWBTC WBTC = IWBTC(0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599);
        cheats.prank(0xCA06411bd7a7296d7dbdd0050DFc846E95fEBEB7);
        WBTC.mint(address(attackContract), 112*10**8);
        cheats.stopPrank();
    }'''
        elif config.contract_name == "bEarnFi_attack":
            self.startStr += '''    constructor() {
        startHoax(address(0x9BEF5148fD530244a14830f4984f2B76BCa0dC58), 90000000000 ether);
        attackContract = new bEarnFi_attack();
        cheats.stopPrank();
        IBUSD BUSD = IBUSD(0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56);
        cheats.prank(0xD2f93484f2D319194cBa95C5171B18C1d8cfD6C4);
        BUSD.mint(7804239e18);
        cheats.prank(0xD2f93484f2D319194cBa95C5171B18C1d8cfD6C4);
        BUSD.transfer(address(attackContract), 7804239e18);
        cheats.stopPrank();
    }
              
            '''
        elif config.contract_name == "Warp_attack":
            self.startStr += '''    constructor() {
        startHoax(address(0x9BEF5148fD530244a14830f4984f2B76BCa0dC58), 90000000000 ether);
        attackContract = new Warp_attack{value: 500000 ether}();
        cheats.stopPrank();
        IDAI DAI = IDAI(0x6B175474E89094C44Da98b954EedeAC495271d0F);
        startHoax(address(0x9759A6Ac90977b93B58547b4A71c78317f391A28));
        DAI.mint(address(attackContract), 5000000 * 10 ** 18 );
        cheats.stopPrank();    
    }
            
            '''
        elif config.contract_name == "valueDeFi_attack":
            self.startStr += '''    constructor() {
        startHoax(address(0x9BEF5148fD530244a14830f4984f2B76BCa0dC58), 90000000000 ether);
        attackContract = new valueDeFi_attack();
        
        cheats.stopPrank();
        IUSDT USDT = IUSDT(0xdAC17F958D2ee523a2206206994597C13D831ec7);
        startHoax(address(0xC6CDE7C39eB2f0F0095F41570af89eFC2C1Ea828));
        USDT.issue(100000000 * 10 ** 6 );
        USDT.transfer(address(attackContract), 100000000 * 10 ** 6);
        cheats.stopPrank();
        
        IDAI DAI = IDAI(0x6B175474E89094C44Da98b954EedeAC495271d0F);
        startHoax(address(0x9759A6Ac90977b93B58547b4A71c78317f391A28));
        DAI.mint(address(attackContract), 116000000 * 10 ** 18 );
        cheats.stopPrank();
    
    }        
'''
        elif config.contract_name == "InverseFi_attack":
            self.startStr += '''    constructor() {
        attackContract = new InverseFi_attack();
        cheats.startPrank(0xCA06411bd7a7296d7dbdd0050DFc846E95fEBEB7);
        IWBTC WBTC = IWBTC(0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599);
        WBTC.mint(address(attackContract), 27000 * 10 ** 8 );
    }
            '''
        elif config.contract_name == "Harvest_USDT_attack":
            self.startStr += '''    constructor() {
        attackContract = new Harvest_USDT_attack();
        IUSDT USDT = IUSDT(0xdAC17F958D2ee523a2206206994597C13D831ec7);
        startHoax(address(0xC6CDE7C39eB2f0F0095F41570af89eFC2C1Ea828));
        USDT.issue(18308555417594 );
        USDT.transfer(address(attackContract), 18308555417594 );
        cheats.stopPrank();
        startHoax(address(0x55FE002aefF02F77364de339a1292923A15844B8));
        IUSDC USDC = IUSDC(0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48);
        address MasterMinter = USDC.masterMinter();
        cheats.stopPrank();
        startHoax(MasterMinter);
        USDC.configureMinter(address(0x9BEF5148fD530244a14830f4984f2B76BCa0dC58), 2**256 -1);
        cheats.stopPrank();
        startHoax(address(0x9BEF5148fD530244a14830f4984f2B76BCa0dC58));
        USDC.mint(address(attackContract), 50000000e6);
    }
            '''
        elif config.contract_name == "Harvest_USDC_attack":
            self.startStr += '''    constructor() {
        attackContract = new Harvest_USDC_attack();
        IUSDT USDT = IUSDT(0xdAC17F958D2ee523a2206206994597C13D831ec7);
        startHoax(address(0xC6CDE7C39eB2f0F0095F41570af89eFC2C1Ea828));
        USDT.issue(50000000 * 10 ** 6 );
        USDT.transfer(address(attackContract), 50000000 * 10 ** 6);
        cheats.stopPrank();
        startHoax(address(0x55FE002aefF02F77364de339a1292923A15844B8));
        IUSDC USDC = IUSDC(0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48);
        address MasterMinter = USDC.masterMinter();
        cheats.stopPrank();
        startHoax(MasterMinter);
        USDC.configureMinter(address(0x9BEF5148fD530244a14830f4984f2B76BCa0dC58), 2**256 -1);
        cheats.stopPrank();
        startHoax(address(0x9BEF5148fD530244a14830f4984f2B76BCa0dC58));
        USDC.mint(address(attackContract), 20000000e6);
    }
        '''
        elif config.contract_name == "ElephantMoney_attack":
            self.startStr +=  '''    constructor() {
        startHoax(address(0x9BEF5148fD530244a14830f4984f2B76BCa0dC58), 90000000000 ether);
        attackContract = new ElephantMoney_attack{value: 100000 ether}();
        cheats.stopPrank();
        IBUSD BUSD = IBUSD(0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56);
        cheats.prank(0xD2f93484f2D319194cBa95C5171B18C1d8cfD6C4);
        BUSD.mint(90000000e18);
        cheats.prank(0xD2f93484f2D319194cBa95C5171B18C1d8cfD6C4);
        BUSD.transfer(address(attackContract), 90000000e18);
        cheats.stopPrank();
    }
        '''
        elif config.contract_name == "OneRing_attack":
            self.startStr +=  '''    constructor() {
        attackContract = new ''' + attackContractName + '''();
        IUSDC usdc = IUSDC(0x04068DA6C83AFCFA0e13ba15A6696662335D5B75);
        address owner_of_usdc = 0xC564EE9f21Ed8A2d8E7e76c085740d5e4c5FaFbE;
        cheats.stopPrank();
        cheats.prank(owner_of_usdc);
        usdc.Swapin(0x33e48143c6ea17476eeabfa202d8034190ea3f2280b643e2570c54265fe33c98, address(attackContract), 150000000*10**6);
    }
        '''
        elif config.contract_name == "ApeRocket_attack":
            self.startStr +=  '''    constructor() {
        attackContract = new ApeRocket_attack();
        cheats.stopPrank();
        cheats.prank(0x73feaa1eE314F8c655E354234017bE2193C9E24E);
        ICAKE CAKE = ICAKE(0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82);
        CAKE.mint(address(attackContract),  1615000e18);
    }
        '''
        elif initialEther == 0 or initialEther is None:
            self.startStr += '''    constructor() {
        startHoax(address(0x9BEF5148fD530244a14830f4984f2B76BCa0dC58), 90000000000 ether);
        attackContract = new ''' + attackContractName + '''();
    }\n'''
        else: 
            self.startStr += '''    constructor() {
        startHoax(address(0x9BEF5148fD530244a14830f4984f2B76BCa0dC58), 90000000000 ether);
        attackContract = new ''' + attackContractName + '''{value: ''' + str(initialEther) + ''' ether}();
    }\n'''



    def initializeAttackContract(self, ActionWrapper):
        self.attack_startStr = ActionWrapper.startStr_contract
        self.attack_endStr = ActionWrapper.endStr_contract

    def addAttackContract(self, contract):
        this_contract = contract.replace(
            "attack(", "attack" + str(self.functionCounter) + "(", 1)
        self.attackContract += this_contract
        self.functionCounter += 1

    # It makes no sense to have updateAttackContract()
    # All the occurance of updateAttackContract() should be replaced by initializeAttackContract + addAttackContract

    # def updateAttackContract(self, contract, start_str, end_str):
    #     self.dataCollectorCount = 0
    #     with open(project_path + "/src/foundryModule/src/attack.sol", "w") as solFile:
    #         solFile.write(start_str + contract + end_str)

    def addDataCollector(self, paraList):
        self.testStr += "    function testExample" + str(self.dataCollectorCount) + "_" \
            + "() public {\n      attackContract.attack" \
            + str(self.functionCounter - 1) + "("

        if len(paraList) == 0:
            self.testStr += ");\n    }\n"
        else:
            for i in range(len(paraList)):
                assert paraList[i] >= 0
                self.testStr = self.testStr + str(paraList[i])
                if i != len(paraList) - 1:
                    self.testStr += ","
                else:
                    self.testStr += ");\n    }\n"

        self.dataCollectorCount += 1
        self.dataPoints.append([paraList, None])
        return self.dataCollectorCount - 1

    def cleanDataCollector(self):
        self.testStr = ""

    def updateDataCollectorContract(self):
        with open(project_path + "/src/foundryModule/src/test/attack.t.sol", "w") as solFile:
            solFile.write(self.startStr + self.testStr + "\n}")

    def executeCollectData(self):

        # Make sure Puppet/PuppetV2 attack.t.sol are empty
        open(project_path + "/src/foundryModule/src/test/Levels/puppet/attack.t.sol", 'w').close()
        open(project_path + "/src/foundryModule/src/test/Levels/puppet-v2/attack.t.sol", 'w').close()


        with open(project_path + "/src/foundryModule/src/attack.sol", "w") as solFile:
            solFile.write(self.attack_startStr +
                          self.attackContract + self.attack_endStr)

        # Not sure if needed
        self.dataCollectorCount = 0
        self.functionCounter = 0
        self.attackContract = ""

        settings = _load_settings()
        endPoint = settings["settings"]["MainnetRpcProvider"]
        if self.ExecutionMode == 1:
            endPoint = settings["settings"]["BSCRpcProvider"]
        elif self.ExecutionMode == 3:
            endPoint = settings["settings"]["FantomRpcProvider"]


        # `--json` gives structured per-test results; see forge/forgeJson.py for why
        # we consume that instead of scraping forge's (now colourless) text output.
        command = "forge test --match-contract attackTester --fork-url " + \
            endPoint + " --fork-block-number " + str(self.blockNum - 1) + " --json"
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