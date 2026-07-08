import os
import sys
import inspect


currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
parentdir = os.path.dirname(parentdir)
sys.path.insert(0, parentdir)
print(parentdir)

from conventions import check_placeholder_count


def buildDVDattackContract(ActionList):
    allActionStr = ""
    for action in ActionList:
        temp = action.actionStr()
        check_placeholder_count(action.__name__, temp, action.numInputs)
        allActionStr += temp

    return allActionStr

def buildDVDCollectorContract(ActionList):
    allCollectorStr = ""
    for action in ActionList[:-1]:
        temp = action.actionStr()
        check_placeholder_count(action.__name__, temp, action.numInputs)
        allCollectorStr += temp
    last = ActionList[-1]
    collector = last.collectorStr()
    check_placeholder_count(last.__name__, collector, last.numInputs)
    allCollectorStr += collector
    return allCollectorStr



