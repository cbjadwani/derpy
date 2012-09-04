from collections import defaultdict


class Token(object):
    def __init__(self, token):
        self.token = token

    def get_token(self):
        return self

    @property
    def nullable(self):
        return self == EPS

    def derive(self, token):
        if self == token:
            return EPS
        return NUL

    def __eq__(self, other):
        if isinstance(other, Grammar):
            return other.get_token() == self
        return isinstance(other, Token) and self.token == other.token

    def __hash__(self):
        return hash(self.token)

    def __and__(self, other):
        x = self
        y = other.get_token() or other
        if x == NUL or y == NUL:
            return NUL
        if x == EPS:
            return y
        if y == EPS:
            return x
        return Grammar(self, CAT, other)

    def __or__(self, other):
        x = self
        y = other.get_token() or other
        if x == y:
            return x
        if x == NUL:
            return y
        if y == NUL:
            return x
        return Grammar(self, ALT, other)

    def __repr__(self):
        return 'Token(%r)' % self.token

    def graph(self, graphed, rank):
        gid = graph_id(self)
        if gid in graphed:
            return
        print
        print '  %s [label="%s" shape=box]' % (gid, str(self.token))
        graphed[gid] = rank


EPS = Token(True)       # epsilon or 'empty' token
NUL = Token(None)       # Null or 'no match' token
LAZY_TOKEN = Token(Ellipsis)
CAT = 'CAT'
ALT = 'ALT'


class Grammar(object):
    def __init__(self, lgrammar, operation=None, rgrammar=None):
        self.lgrammar = lgrammar.get_token() or lgrammar
        self.operation = operation
        self.rgrammar = operation and rgrammar.get_token() or rgrammar
        self._derivations = {}
        self._nullable = None

    def get_token(self):
        if self.operation is None and isinstance(self.lgrammar, Token):
            return self.lgrammar
        return None

    def _fold(self):
        assert self.operation is CAT
        l = self.lgrammar
        r = self.rgrammar
        seen = [self]
        while isinstance(l, Grammar):
            if l.operation is None:
                l = l.lgrammar
                self.lgrammar = l
                continue
            if l.operation is not CAT:
                break
            if l in seen:
                # Infinite left recursion, can not match anything
                print ' .==.'
                self.lgrammar = NUL
                self.operation = None
                self.rgrammar = None
                return
            seen.append(l)
            l, r = l.lgrammar, Grammar(l.rgrammar, CAT, r)
        self.lgrammar = l
        self.rgrammar = r

    def __and__(self, other):
        x = self.get_token() or self
        y = other.get_token() or other
        if x == NUL or y == NUL:
            return NUL
        if x == EPS:
            return y
        if y == EPS:
            return x
        res = Grammar(x, CAT, y)
        res._fold()
        r = res.rgrammar
        if isinstance(r, Grammar) and r.operation is CAT:
            r._fold()
        return res

    def __or__(self, other):
        x = self.get_token() or self
        y = other.get_token() or other
        if x == NUL:
            return y
        if y == NUL:
            return x
        if x is y:
            return x
        return Grammar(x, ALT, y)

    @property
    def nullable(self):
        if self._nullable is None:
            self._nullable = self._is_nullable()
        return self._nullable

    def _is_nullable(self):
        self._nullable = False  # Initail value to break recursions
        l = self.lgrammar
        r = self.rgrammar
        if self.operation is None:
            return self.lgrammar.nullable
        if self.operation is CAT:
            return l.nullable and r.nullable
        if self.operation is ALT:
            return l.nullable or r.nullable
        assert False, "Bad! %s" % self.operation

    def derive(self, token):
        try:
            return self._derivations[token]
        except KeyError:
            pass
        cached = self._derivations[token] = Grammar(LAZY_TOKEN, ALT, EPS)
        res = self._derive(token)
        assert res is not cached
        if not isinstance(res, Grammar) or res.is_lazy():
            cached.lgrammar = res
            cached.operation = None
            cached.rgrammar = None
            if isinstance(res, Grammar) and res.is_lazy():
                print ' --x--', graph_id(res), graph_id(cached)
        else:
            cached.lgrammar = res.lgrammar
            cached.operation = res.operation
            cached.rgrammar = res.rgrammar
            if cached.operation is CAT:
                cached._fold()
        return cached

    def _derive(self, token):
        if self.lgrammar == LAZY_TOKEN:
            raise Exception('Fake!')
        l = self.lgrammar
        r = self.rgrammar
        res = None
        if self.operation is None:
            res = l.derive(token)
        elif self.operation is CAT:
            d1 = l.derive(token) & r
            if not l.nullable:
                res = d1
            else:
                res = d1 | r.derive(token)
        elif self.operation is ALT:
            d1 = l.derive(token)
            d2 = r.derive(token)
            res = d1 | d2
        else:
            assert False, "Bad! %s" % self.operation
        assert res is not None
        return res

    def match_(self, tokens):
        l = self
        for token in tokens:
            l = l.derive(token)
            if l.get_token() == NUL:
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
        return graphed

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

    def any_lazy(self, checked=None):
        for i in self:
            if isinstance(i, Grammar) and i.is_lazy():
                return True
        return False

    def derive_many(self, tokens):
        d = self
        for token in tokens:
            d = d.derive(token)
            if d is NUL:
                break
        return d

    def starplus(self):
        eps = Grammar(EPS)
        plus = Grammar(eps, CAT, self)
        star = Grammar(eps, ALT, plus)
        plus.lgrammar = star
        return (star, plus)

    def star(self):
        return self.starplus()[0]

    def plus(self):
        return self.starplus()[1]


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

a = char('a')
S = (a & char('(') & a & char(')')) | Grammar(EPS)
#S.lgrammar.lgrammar.lgrammar.lgrammar = S
#S.lgrammar.lgrammar.rgrammar = S
S.lgrammar.rgrammar.rgrammar.lgrammar = S
S.lgrammar.lgrammar = S

s = (a & char('+') & a) | char('1')
s.lgrammar.rgrammar.rgrammar = s
s.lgrammar.lgrammar = s
#s.lgrammar.lgrammar.lgrammar = s
#s.lgrammar.rgrammar = s
"""
S = (((S o) S) c) | e
dS = (dS
"""
