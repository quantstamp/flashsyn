import os
import sys
import inspect


currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
parentdir = os.path.dirname(parentdir)
sys.path.insert(0, parentdir) 
print(parentdir)


def buildDVDattackContract(ActionList):
    allActionStr = ""
    for i in range(len(ActionList)):
        temp = ActionList[i].actionStr()
        allActionStr += temp
    
    return allActionStr

def buildDVDCollectorContract(ActionList):
    allCollectorStr = ""
    for i in range(len(ActionList) - 1):
        temp = ActionList[i].actionStr()
        allCollectorStr += temp
    allCollectorStr += ActionList[-1].collectorStr()
    return allCollectorStr



