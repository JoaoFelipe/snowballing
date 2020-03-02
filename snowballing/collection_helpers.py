import functools


class VarAccessor(object):
    """Define functions for accessing atributtes and items using a variable as a map"""

    def __init__(self):
        self.cvar = None
    
    def dget(self, collection, key, default=None, cvar=None):
        return collection.get((cvar or self.cvar)[key], default)

    def dset(self, collection, key, value, cvar=None):
        collection[(cvar or self.cvar)[key]] = value

    def dhas(self, collection, key, cvar=None):
        return (cvar or self.cvar)[key] in collection

    def ddel(self, collection, key, cvar=None):
        del collection[(cvar or self.cvar)[key]]

    def oget(self, obj, key, default=None, cvar=None):
        return getattr(obj, (cvar or self.cvar)[key], default)

    def oset(self, obj, key, value, cvar=None):
        setattr(obj, (cvar or self.cvar)[key], value)

    def ohas(self, obj, key, cvar=None):
        return hasattr(obj, (cvar or self.cvar)[key])

    def odel(self, obj, key, cvar=None):
        del obj[(cvar or self.cvar)[key]]
    

var_accessor = VarAccessor()
dget = var_accessor.dget
dset = var_accessor.dset
dhas = var_accessor.dhas
ddel =var_accessor.ddel
oget = var_accessor.oget
oset = var_accessor.oset
ohas = var_accessor.ohas
odel = var_accessor.odel


def consume(info, key):
    """Consumes key from dict

    Arguments:

    * `info` -- dict
    * `key` -- key

    Doctest:

    .. doctest::

        >>> info = {'abc': 1, 'def': 2}
        >>> consume(info, 'abc')
        1
        >>> info
        {'def': 2}
        >>> consume(info, 'abc') is None
        True
    """
    if key not in info:
        return None
    result = info[key]
    del info[key]
    return result


def consume_key(collection, key, use_key):
    """Consume key from collection based on use_key"""
    if use_key is True:
        return consume(collection, key)
    elif use_key:
        return consume(collection, use_key)
    else:
        return collection.get(key)


def setitem(info, key, value):
    """Set item in dict info if value is not None 

    Doctest:

    .. doctest::

        >>> info = {}
        >>> setitem(info, 'def', 2)
        >>> info
        {'def': 2}
        >>> setitem(info, 'abc', None)
        >>> info
        {'def': 2}
    """
    if value is not None:
        info[key] = value


def callable_get(collection, key, default=None, args=[]):
    """Get item from collection. Return collection applied to args, if it is callable"""
    result = collection.get(key, default)
    if callable(result):
        return result(*args)
    return result


def remove_empty(elements):
    """Remove empty elements from list"""
    for element in elements:
        if element:
            yield element


def define_cvar(cvar):
    var_accessor.cvar = cvar
