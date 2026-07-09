class Action():    
    @classmethod
    def string(cls):
        return cls.__name__

    def __str__(self):
        return self.__name__



def ToString(action_list):
    temp = ""
    for ii in range(len(action_list)):
        if ii != len(action_list) - 1:
            temp += action_list[ii].__name__ + ", "
        else:
            temp += action_list[ii].__name__
    return temp

