"""Analizador léxico de OxigenNative (PLY)."""
import ply.lex as lex
from ply.lex import TOKEN

from .errors import LEXICO

reserved = {
    "fn": "FN", "let": "LET", "mut": "MUT", "if": "IF", "else": "ELSE",
    "while": "WHILE", "loop": "LOOP", "match": "MATCH", "break": "BREAK",
    "continue": "CONTINUE", "return": "RETURN", "true": "TRUE", "false": "FALSE",
    "i32": "I32", "f64": "F64", "bool": "BOOL", "char": "CHAR",
    "String": "STRING_T", "str": "STR_T",
    "struct": "STRUCT", "for": "FOR", "in": "IN",
}

ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'", "0": "\0"}


def line_col(text, pos):
    """Convierte un offset del texto fuente en (línea, columna), ambos base 1."""
    line = text.count("\n", 0, pos) + 1
    col = pos - (text.rfind("\n", 0, pos) + 1) + 1
    return line, col


def unescape(body, on_error):
    out = []
    i = 0
    while i < len(body):
        c = body[i]
        if c == "\\" and i + 1 < len(body):
            n = body[i + 1]
            if n in ESCAPES:
                out.append(ESCAPES[n])
                i += 2
            elif n == "u" and body[i + 2:i + 3] == "{" and "}" in body[i:]:
                j = body.index("}", i)
                try:
                    out.append(chr(int(body[i + 3:j], 16)))
                except ValueError:
                    on_error(f"Secuencia de escape no válida: '\\u{{{body[i + 3:j]}}}'")
                i = j + 1
            else:
                on_error(f"Secuencia de escape no válida: '\\{n}'")
                out.append(n)
                i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


class OxLexer:
    tokens = [
        "ID", "INT", "FLOAT", "STRING", "CHAR_LIT", "LABEL", "PRINTLN", "PRINT", "WILDCARD",
        "PLUS", "MINUS", "TIMES", "DIVIDE", "MOD",
        "ASSIGN", "PLUSEQ", "MINUSEQ", "TIMESEQ", "DIVEQ", "MODEQ",
        "EQ", "NE", "LT", "GT", "LE", "GE", "AND", "OR", "NOT", "AMP", "PIPE",
        "ARROW", "FATARROW", "COLONCOLON", "DOTDOT",
        "LPAREN", "RPAREN", "LBRACE", "RBRACE", "LBRACKET", "RBRACKET",
        "COMMA", "SEMI", "COLON", "DOT",
    ] + sorted(set(reserved.values()))

    t_ignore = " \t\r"

    def __init__(self, errors):
        self.errors = errors
        self.lexer = None

    def build(self):
        self.lexer = lex.lex(module=self)
        return self

    def input(self, text):
        self.text = text
        self.lexer.lineno = 1
        self.lexer.input(text)

    def token(self):
        return self.lexer.token()

    # ---------------------------------------------------------------- utilidades
    def _err(self, desc, t_or_pos):
        pos = t_or_pos if isinstance(t_or_pos, int) else t_or_pos.lexpos
        line, col = line_col(self.text, pos)
        self.errors.add(LEXICO, desc, line, col)

    # ---------------------------------------------------------------- comentarios
    @TOKEN(r"//[^\n]*")
    def t_COMMENT_LINE(self, t):
        pass

    @TOKEN(r"/\*(.|\n)*?\*/")
    def t_COMMENT_BLOCK(self, t):
        t.lexer.lineno += t.value.count("\n")

    @TOKEN(r"/\*(.|\n)*")
    def t_COMMENT_UNCLOSED(self, t):
        self._err("Comentario de bloque sin cierre ('*/').", t)
        t.lexer.lineno += t.value.count("\n")

    # ---------------------------------------------------------------- cadenas
    @TOKEN(r'r\#"(.|\n)*?"\#')
    def t_STRING_RAW_HASH(self, t):
        t.type = "STRING"
        t.lexer.lineno += t.value.count("\n")
        t.value = t.value[3:-2]
        return t

    @TOKEN(r'r"[^"]*"')
    def t_STRING_RAW(self, t):
        t.type = "STRING"
        t.lexer.lineno += t.value.count("\n")
        t.value = t.value[2:-1]
        return t

    @TOKEN(r'[“"]([^"“”\\]|\\(.|\n))*["”]')
    def t_STRING(self, t):
        t.lexer.lineno += t.value.count("\n")
        t.value = unescape(t.value[1:-1], lambda m: self._err(m, t))
        return t

    @TOKEN(r'["“]([^"“”\\]|\\(.|\n))*')
    def t_STRING_UNCLOSED(self, t):
        self._err("Cadena de texto sin cerrar.", t)
        t.lexer.lineno += t.value.count("\n")

    @TOKEN(r"'([^'\\\n]|\\(u\{[0-9a-fA-F]+\}|.))'")
    def t_CHAR_LIT(self, t):
        body = unescape(t.value[1:-1], lambda m: self._err(m, t))
        t.value = body[0] if body else "\0"
        return t

    @TOKEN(r"'[A-Za-z_][A-Za-z0-9_]*")
    def t_LABEL(self, t):
        return t

    # ---------------------------------------------------------------- números
    @TOKEN(r"\d+\.\d+")
    def t_FLOAT(self, t):
        t.value = float(t.value)
        return t

    @TOKEN(r"\d+")
    def t_INT(self, t):
        t.value = int(t.value)
        return t

    # ---------------------------------------------------------------- macros e identificadores
    @TOKEN(r"println!")
    def t_PRINTLN(self, t):
        return t

    @TOKEN(r"print!")
    def t_PRINT(self, t):
        return t

    @TOKEN(r"[A-Za-z_][A-Za-z0-9_]*")
    def t_ID(self, t):
        if t.value == "_":
            t.type = "WILDCARD"
        else:
            t.type = reserved.get(t.value, "ID")
        return t

    @TOKEN(r"\n+")
    def t_newline(self, t):
        t.lexer.lineno += len(t.value)

    # ---------------------------------------------------------------- operadores
    t_ARROW = r"->"
    t_FATARROW = r"=>"
    t_COLONCOLON = r"::"
    t_DOTDOT = r"\.\."
    t_PLUSEQ = r"\+="
    t_MINUSEQ = r"-="
    t_TIMESEQ = r"\*="
    t_DIVEQ = r"/="
    t_MODEQ = r"%="
    t_EQ = r"=="
    t_NE = r"!="
    t_LE = r"<="
    t_GE = r">="
    t_AND = r"&&"
    t_OR = r"\|\|"
    t_PLUS = r"\+"
    t_MINUS = r"-"
    t_TIMES = r"\*"
    t_DIVIDE = r"/"
    t_MOD = r"%"
    t_ASSIGN = r"="
    t_LT = r"<"
    t_GT = r">"
    t_NOT = r"!"
    t_AMP = r"&"
    t_PIPE = r"\|"
    t_LPAREN = r"\("
    t_RPAREN = r"\)"
    t_LBRACE = r"\{"
    t_RBRACE = r"\}"
    t_LBRACKET = r"\["
    t_RBRACKET = r"\]"
    t_COMMA = r","
    t_SEMI = r";"
    t_COLON = r":"
    t_DOT = r"\."

    def t_error(self, t):
        ch = t.value[0]
        self._err(f"Carácter no reconocido: '{ch}'", t)
        t.lexer.skip(1)
