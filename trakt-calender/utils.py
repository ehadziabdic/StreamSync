class Data:
    def __init__(self, data):
        if data:
            self.__dict__.update(data)

    def __repr__(self):
        return str(self.__dict__)

def padWithZero(s, length):
    # Modern Python way to pad strings with zeros
    return str(s).zfill(length)