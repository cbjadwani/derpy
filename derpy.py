from utils import memoize


class Token(object):
    def __init__(self, token):
        self.token = token

    def get_token(self):
        return self

    def __eq__(self, other):
        if isinstance(other, Language):
            return other.get_token() == self
        return other is not None and self.token == other.token

    def __repr__(self):
        return 'Token(%r)' % self.token


EPS = Token('')         # epsilon, 'empty' token
NUL = Token(None)       # Null, no match token


class Op(object):
    def __init__(self, opname):
        self.opname = opname

    def __repr__(self):
        return 'Op(%r)' % self.opname


CAT = Op('CAT')
ALT = Op('ALT')


class Language(object):
    def __init__(self, language1, operation=None, language2=None):
        self.language1 = language1.get_token() or language1
        self.operation = operation
        self.language2 = operation and language2.get_token() or language2
        self._nullable = None
        self._derivations = {}

    def get_token(self):
        if self.operation is None and isinstance(self.language1, Token):
            return self.language1
        return None

    def __add__(self, other):
        other_token = other.get_token()
        self_token = self.get_token()
        if other_token == NUL or self_token == NUL:
            return Language(NUL)
        if other_token == EPS:
            return self
        if self_token == EPS:
            return Language(other_token) if other_token else other
        return Language(self, CAT, other)

    def __or__(self, other):
        other_token = other.get_token()
        self_token = self.get_token()
        if other_token == NUL:
            return self
        if self_token == NUL:
            return Language(other_token) if other_token else other
        if self is other:
            return self
        return Language(self, ALT, other)

    def starplus(self):
        eps = Language(EPS)
        plus = Language(self, CAT, eps)
        star = Language(eps, ALT, plus)
        plus.language2 = star
        return (star, plus)

    def star(self):
        return self.starplus()[0]

    def plus(self):
        return self.starplus()[1]

    @property
    def nullable(self):
        if self._nullable is None:
            self._nullable = self._is_nullable()
        return self._nullable

    def _is_nullable(self):
        self._nullable = False
        if self.operation is None:
            self_token = self.get_token()
            if self_token == EPS:
                return True
            elif self_token:
                return False
            else:
                return self.language1.nullable
        l1 = self.language1
        l2 = self.language2
        if isinstance(l1, Token):
            l1 = Language(l1)
        if isinstance(l2, Token):
            l2 = Language(l2)
        if self.operation is CAT:
            return l1.nullable and l2.nullable
        if self.operation is ALT:
            return l1.nullable or l2.nullable
        assert False, "Bad! %s" % self.operation

    def derive(self, token):
        d = self._derivations.get(token)
        if d is not None: return d
        self._derivations[token] = d = Language(NUL)
        if self.operation is None:
            self_token = self.get_token()
            if self_token == token:
                d.language1 = EPS
                return d
            elif self_token:
                return d
            else:
                self._derivations[token] = self.language1.derive(token)
                return self._derivations[token]
        l1 = self.language1
        l2 = self.language2
        if isinstance(l1, Token):
            l1 = Language(l1)
        if isinstance(l2, Token):
            l2 = Language(l2)
        if self.operation is CAT:
            d1 = l1.derive(token) + l2
            if not l1.nullable:
                self._derivations[token] = d1
                return self._derivations[token]
            self._derivations[token] = d1 | l2.derive(token)
            return self._derivations[token]
        if self.operation is ALT:
            d1 = l1.derive(token)
            d2 = l2.derive(token)
            self._derivations[token] = d1 | d2
            return self._derivations[token]
        assert False, "Bad! %s" % self.operation

    def match(self, raw_tokens):
        tokens = map(Token, raw_tokens)
        return self.match_(tokens)

    def match_(self, tokens):
        l = self
        for token in tokens:
            l = l.derive(token)
            if l.get_token() == NUL:
                return False
        return l.nullable


chr_range = lambda a, b: ''.join(map(chr, range(ord(a), ord(b)+1)))
char = lambda c: Language(Token(c))
from_string = lambda s: reduce(lambda a, b: a | b, map(char, s))
alpha = from_string(chr_range('A', 'Z') + chr_range('a', 'z'))
num = from_string('0123456789')
word = alpha + (alpha | num).star()
