from collections import defaultdict


EPS_TOKEN_VALUE = True
NUL_TOKEN_VALUE = None


class Token(object):
    def __init__(self, token):
        self.token = token
        self.nullable = (token == EPS_TOKEN_VALUE)

    def get_value(self):
        return self

    def derive(self, token):
        if self == token:
            return EPS
        return NUL

    def __eq__(self, other):
        if isinstance(other, Grammar):
            other = other.get_value()
        return isinstance(other, Token) and self.token == other.token

    def __hash__(self):
        return hash(self.token)

    def __and__(self, other):
        x = self
        y = other.get_value()
        if x == NUL or y == NUL:
            return NUL
        if x == EPS:
            return y
        if y == EPS:
            return x
        return Grammar(x, CAT, y)

    def __or__(self, other):
        x = self
        y = other.get_value()
        if x == y:
            return x
        if x == NUL:
            return y
        if y == NUL:
            return x
        return Grammar(x, ALT, y)

    def __repr__(self):
        return 'Token(%r)' % self.token

    def graph(self, graphed, rank):
        gid = graph_id(self)
        if gid in graphed:
            graphed[gid] = min(rank, graphed[gid])
            return
        print
        print '  %s [label="%s" shape=box]' % (gid, str(self.token))
        graphed[gid] = rank


EPS = Token(EPS_TOKEN_VALUE)    # epsilon or 'empty' token
NUL = Token(NUL_TOKEN_VALUE)    # Null or 'no match' token
LAZY_TOKEN = Token(Ellipsis)
CAT = 'CAT'
ALT = 'ALT'


class Grammar(object):
    def __init__(self, lgrammar, operation=None, rgrammar=None):
        self.lgrammar = lgrammar.get_value()
        self.operation = operation
        self.rgrammar = operation and rgrammar.get_value()
        self._derivations = {}
        self._nullable = None

    def get_value(self):
        if self.operation is None:
            return self.lgrammar
        return self

    def __and__(self, other):
        x = self.get_value()
        y = other.get_value()
        if x == NUL or y == NUL:
            return NUL
        if x == EPS:
            return y
        if y == EPS:
            return x
        result = Grammar(x, CAT, y)
        result._lfold_cats()
        return result

    def _lfold_cats(self):
        assert self.operation is CAT
        l = self.lgrammar
        r = self.rgrammar
        seen = [self]
        while isinstance(l, Grammar):
            if l.operation is None:
                parent = seen[-1]
                seen.append(l)
                parent.lgrammar = l = l.lgrammar
                continue
            elif l.operation is CAT:
                if l in seen:
                    # Infinite left recursion, can not match anything
                    self.setvalues(NUL, None, None)
                    return
                seen.append(l)
                l, r = l.lgrammar, l.rgrammar & r
            else:
                break
        self.lgrammar = l
        self.rgrammar = r

    def __or__(self, other):
        x = self.get_value()
        y = other.get_value()
        if x == NUL:
            return y
        if y == NUL:
            return x
        if x == y:
            return x
        return Grammar(x, ALT, y)

    @property
    def nullable(self):
        if self._nullable is None:
            self._nullable = ''     # A non-None 'False'y value to indicate calculation is in progress
            _nullable = self._is_nullable()
            if _nullable == '':
                raise Exception('Could not decide if this not is nullable')
            self._nullable = _nullable
        return self._nullable

    def peek_nullable(self):
        if self._nullable is not None:
            return self._nullable
        _nullable = self._is_nullable()
        if isinstance(_nullable, bool):
            self._nullable = _nullable
        return _nullable

    def _is_nullable(self):
        l = self.lgrammar
        r = self.rgrammar
        if self.operation is None:
            return l.nullable
        elif self.operation is CAT:
            ln = l.nullable if isinstance(l, Token) else l.peek_nullable()
            rn = r.nullable if isinstance(r, Token) else r.peek_nullable()
            if ln is False or rn is False:
                return False
            return ln and rn
        elif self.operation is ALT:
            ln = l.nullable if isinstance(l, Token) else l.peek_nullable()
            rn = r.nullable if isinstance(r, Token) else r.peek_nullable()
            if ln is True or rn is True:
                return True
            if not isinstance(ln, bool):
                return ln
            if not isinstance(rn, bool):
                return rn
            return ln or rn
        else:
            assert False, "Bad! %s" % self.operation

    def singles_fold(self):
        for g in self:
            if not isinstance(g, Grammar):
                continue
            while True:
                l = g.lgrammar
                if not (isinstance(l, Grammar) and l.operation is None):
                    break
                g.lgrammar = l.lgrammar
            if self.operation is not None:
                while True:
                    r = g.rgrammar
                    if not (isinstance(r, Grammar) and r.operation is None):
                        break
                    g.rgrammar = r.rgrammar
            elif isinstance(self.lgrammar, Grammar):
                l = self.lgrammar
                self.lgrammar = l.lgrammar
                self.operation = l.operation
                self.rgrammar = l.rgrammar

    def derive(self, token):
        try:
            return self._derivations[token]
        except KeyError:
            pass
        temp = self._derivations[token] = Grammar.create_lazy()
        result = self._derive(token)
        assert result is not temp
        temp.setvalues(result, None, None)
        self._derivations[token] = result
        return result

    def _derive(self, token):
        if self.lgrammar == LAZY_TOKEN:
            raise Exception('Fake!')
        l = self.lgrammar.get_value()
        r = self.rgrammar and self.rgrammar.get_value()
        self.lgrammar = l
        self.rgrammar = r
        result = None
        if self.operation is None:
            result = l.derive(token)
        elif self.operation is CAT:
            d_l = l.derive(token)
            if not l.nullable:
                result = d_l & r
            else:
                d_r = r.derive(token)
                result = (d_l & r) | d_r
        elif self.operation is ALT:
            d_l = l.derive(token)
            d_r = r.derive(token)
            result = d_l | d_r
        else:
            assert False, "Bad! %s" % self.operation
        return result

    def match_(self, tokens):
        l = self
        for token in tokens:
            l = l.derive(token)
            global FOLD_SINGLES
            if FOLD_SINGLES:
                l.singles_fold()
            if l.get_value() == NUL:
                return False
        return l.nullable

    def match(self, raw_tokens):
        tokens = map(Token, raw_tokens)
        return self.match_(tokens)

    def graph(self, graphed=None, rank=0):
        firstcall = rank == 0
        gid = graph_id(self)
        if firstcall:
            graphed = {}
            print 'digraph derpy {'
            print 'graph [layout=dot rankdir=TB ordering=out]'
        elif gid in graphed:
            graphed[gid] = min(rank, graphed[gid])
            return
        l, r = self.lgrammar, self.rgrammar
        lid, rid = graph_id(l), graph_id(r)
        points_up = lambda xid: graphed.get(xid, 999999) < rank
        print
        print '  %s[label="%s"%s]' % (gid, self.operation or 'S', ' shape=invhouse' if firstcall else '')
        print '    %s -> %s[label="L"%s]' % (gid, lid, ' constraint=false' if points_up(lid) else '')
        if self.operation is not None:
            print '    %s -> %s[label="R"%s]' % (gid, rid, ' constraint=false' if points_up(rid) else '')
        graphed[gid] = rank
        l.graph(graphed, rank+1)
        if self.operation is not None:
            r.graph(graphed, rank+1)
        if firstcall:
            ranks = defaultdict(list)
            for xid, rank in graphed.items():
                ranks[rank].append(xid)
            for rank in sorted(ranks.keys()[1:]):
                print '  {rank=same; %s}' % ' '.join(ranks[rank])
            print '}'

    def __iter__(self):
        return self._iterate()

    def _iterate(self, iterated=None):
        l = self.lgrammar
        r = self.rgrammar
        sid = id(self)
        if iterated is None:
            iterated = {}
        else:
            if sid in iterated:
                return
        iterated[sid] = True
        assert l
        if isinstance(l, Grammar):
            for i in l._iterate(iterated):
                yield i
        else:
            yield l
        yield self
        if isinstance(r, Grammar):
            for i in r._iterate(iterated):
                yield i
        elif r is not None:
            yield r

    @classmethod
    def create_lazy(cls):
        return cls(LAZY_TOKEN, ALT, EPS)

    def is_lazy(self):
        if self.lgrammar == LAZY_TOKEN:
            if self.operation is ALT and self.rgrammar == EPS:
                return True
            raise Exception("Fake lazy!")
        return False

    def setvalues(self, l, o, r):
        self.lgrammar = l
        self.operation = o
        self.rgrammar = r

    def copyfrom(self, other):
        self.lgrammar = other.lgrammar
        self.operation = other.operation
        self.rgrammar = other.rgrammar

    def any_lazy(self):
        for i in self:
            if isinstance(i, Grammar) and i.is_lazy():
                return True
        return False

    def derive_raw(self, raw_tokens):
        d = self
        for token in map(Token, raw_tokens):
            d = d.derive(token)
            global FOLD_SINGLES
            if FOLD_SINGLES:
                d.singles_fold()
            if d is NUL:
                break
        return d

    def starplus(self):
        plus = Grammar(self, CAT, EPS)
        star = Grammar(EPS, ALT, plus)
        plus.rgrammar = star
        return (star, plus)

    def star(self):
        return self.starplus()[0]

    def plus(self):
        return self.starplus()[1]


class SymbolDict(dict):
    def __init__(self, language):
        self.language = language
        self.gdict = defaultdict(Grammar.create_lazy)

    def __getitem__(self, key):
        return self.gdict[key]

    def __setitem__(self, key, value):
        g = self.gdict[key]
        if not g.is_lazy():
            print 'WARNING: assigning to non-lazy symbol'
        if isinstance(value, Grammar):
            g.lgrammar = value.lgrammar
            g.operation = value.operation
            g.rgrammar = value.rgrammar
        else:
            g.lgrammar = value
            g.operation = None
            g.rgrammar = None


class Language(object):

    def __init__(self):
        self.NT = SymbolDict(self)
        self._tokens = {}

    def T(self, raw_token):
        return self._tokens.setdefault(raw_token, Token(raw_token))


def graph_id(obj):
    ID = str(abs(id(obj)))
    c = chr(ord(ID[0]) + ord('A') - ord('0'))
    return c + ID[1:]


chr_range = lambda a, b: ''.join(map(chr, range(ord(a), ord(b)+1)))
char = lambda c: Grammar(Token(c))
anychar = lambda s: reduce(lambda a, b: a | b, map(char, s))
alpha = anychar(chr_range('A', 'Z') + chr_range('a', 'z'))
num = anychar('0123456789')
word = alpha & (alpha | num).star()

a = Token('a')
b = Token('b')

S = Grammar.create_lazy()
S.copyfrom((S & char('(') & S & char(')')) | EPS)

s = Grammar.create_lazy()
s.copyfrom(s & char('+') & s | char('1'))

top = Grammar.create_lazy()
bot = top | EPS
x = a & bot
y = bot & b
top.copyfrom(x & y)

lisp = Grammar.create_lazy()
lispitem = Grammar.create_lazy()
lisp.copyfrom((char('(') & lispitem & char(')')) | char('s'))
lispitem.copyfrom((lispitem & lisp) | EPS)
FOLD_SINGLES = False


def test():
    assert s.match('') == False
    assert s.match('1+1') == True
    assert s.match('1') == True
    assert s.match('1+' * 10 + '+') == False

    assert S.match('') == True
    assert S.match('(((()())))') == True
    assert S.match('()()()((') == False

    assert lisp.match('((s(s)))') == True
    assert lisp.match('s') == True
    assert lisp.match('()') == True


def prof(n=10, best=3):
    import time
    times = []
    for _ in range(n):
        for i in (set(s) | {s}):
            if isinstance(i, Grammar):
                i._derivations.clear()
        tstart = time.time()
        s.match('1' + '+1' * 150)
        tend = time.time()
        times.append(tend-tstart)
    return sum(sorted(times)[:best])/min(n, best)
