from functools import partial

class memoize_recursive(object):
    """cache the return value of a method

    Original source: code.activestate.com/recipes/577452-a-memoize-decorator-for-instance-methods/

    Added the ``default`` param so that non-terminating recursive calls can
    be given a default value which will break the recursion and allows the
    top most call to return a value (could be other than the default) which
    will be cached.

    This class is meant to be used as a decorator of methods. The return value
    from a given method invocation will be cached on the instance whose method
    was invoked. All arguments passed to a method decorated with memoize must
    be hashable.

    If a memoized method is invoked directly on its class the result will not
    be cached. Instead the method will be invoked like a static method:
    class Obj(object):
        @memoize
        def add_to(self, arg):
            return self + arg
    Obj.add_to(1) # not enough arguments
    Obj.add_to(1, 2) # returns 3, result is not cached
    """
    def __init__(self, func, **kwargs):
        self.func = func
        try:
            self.default_value = kwargs.pop('default')
        except KeyError:
            pass
        if kwargs:
            raise TypeError('Got unexpected kwargs: %s' % kwargs.keys())

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self.func
        return partial(self, obj)

    def __call__(self, *args, **kw):
        obj = args[0]
        try:
            cache = obj.__cache
        except AttributeError:
            cache = obj.__cache = {}
        key = (self.func, args[1:], frozenset(kw.items()))
        try:
            res = cache[key]
        except KeyError:
            if hasattr(self, 'default_value'):
                default_value = self.default_value
                cache[key] = default_value
            res = cache[key] = self.func(*args, **kw)
        return res


if __name__ == "__main__":
    # example usage
    class Test(object):
        v = 0
        @memoize
        def inc_add(self, arg):
            self.v += 1
            return self.v + arg

    t = Test()
    assert t.inc_add(2) == t.inc_add(2)
    assert Test.inc_add(t, 2) != Test.inc_add(t, 2)
