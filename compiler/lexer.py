"""Análisis léxico de OxigenNative con PLY"""

import ply.lex as lex

KEYWORDS = {
    "fn": "FN", "let": "LET", "mut": "MUT", "if": "IF", "else": "ELSE",
    "while": "WHILE", "loop": "LOOP", "for": "FOR", "in": "IN",
    "match": "MATCH", "break": "BREAK", "continue": "CONTINUE",
    "return": "RETURN", "true": "TRUE", "false": "FALSE", "as": "AS",
    "struct": "STRUCT",
    "i32": "T_I32", "f64": "T_F64", "bool": "T_BOOL", "char": "T_CHAR",
    "String": "T_STRING", "str": "T_STR", "Vec": "T_VEC",
}

tokens = [
    "ID", "STRUCT_NAME", "INT", "FLOAT", "STRING", "CHAR", "LABEL", "PRINTLN", "PRINT",
    "BLOCK_COMMENT",
    "PLUS", "MINUS", "STAR", "SLASH", "PERCENT",
    "EQ", "NE", "LE", "GE", "LT", "GT", "AND", "OR", "NOT",
    "ASSIGN", "PLUSEQ", "MINUSEQ", "STAREQ", "SLASHEQ", "PERCENTEQ",
    "LPAREN", "RPAREN", "LBRACE", "RBRACE", "LBRACKET", "RBRACKET",
    "COMMA", "SEMI", "COLON", "COLONCOLON", "DOT", "DOTDOT", "DOTDOTEQ",
    "ARROW", "FATARROW", "AMP", "PIPE", "UNDERSCORE",
] + sorted(set(KEYWORDS.values()))

ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'", "0": "\0"}


class OxigenLexer:
    tokens = tokens

    def __init__(self, errors):
        self.errors = errors
        self.lexer = lex.lex(module=self, debug=False)
        self.data = ""

    # -- utilidades ---------------------------------------------------------
    def input(self, data):
        self.data = data
        self.lexer.lineno = 1
        self.lexer.input(data)

    def token(self):
        return self.lexer.token()

    def col(self, pos):
        return pos - self.data.rfind("\n", 0, pos)

    def _err(self, msg, t):
        self.errors.lexico(msg, t.lineno, self.col(t.lexpos))

    def _decode(self, body, t, quote):
        """Procesa secuencias de escape de cadenas y caracteres."""
        out, i = [], 0
        while i < len(body):
            c = body[i]
            if c == "\\" and i + 1 < len(body):
                n = body[i + 1]
                if n in ESCAPES:
                    out.append(ESCAPES[n])
                    i += 2
                    continue
                if n == "u" and i + 2 < len(body) and body[i + 2] == "{":
                    j = body.find("}", i)
                    try:
                        out.append(chr(int(body[i + 3:j], 16)))
                        i = j + 1
                        continue
                    except (ValueError, OverflowError):
                        pass
                self._err(f"Secuencia de escape no válida '\\{n}'.", t)
                out.append(n)
                i += 2
                continue
            out.append(c)
            i += 1
        return "".join(out)

    # -- reglas (el orden de definición es el orden de prioridad) -----------
    t_ignore = " \t\r"
    t_ignore_LINE_COMMENT = r"//[^\n]*"

    def t_BLOCK_COMMENT(self, t):
        r"/\*(.|\n)*?\*/"
        t.lexer.lineno += t.value.count("\n")
        return None  # los comentarios no generan tokens

    def t_NEWLINE(self, t):
        r"\n+"
        t.lexer.lineno += len(t.value)

    def t_RAWSTRING_HASH(self, t):
        r'r\#"(.|\n)*?"\#'
        t.type = "STRING"
        t.value = t.value[3:-2]
        t.lexer.lineno += t.value.count("\n")
        return t

    def t_RAWSTRING(self, t):
        r'r"[^"]*"'
        t.type = "STRING"
        t.value = t.value[2:-1]
        t.lexer.lineno += t.value.count("\n")
        return t

    def t_STRING(self, t):
        r'"(\\.|[^"\\])*"'
        raw = t.value[1:-1]
        t.value = self._decode(raw, t, '"')
        t.lexer.lineno += raw.count("\n")
        return t

    def t_CHAR(self, t):
        r"'(\\.|\\u\{[0-9a-fA-F]+\}|[^\\'\n])'"
        body = t.value[1:-1]
        t.value = self._decode(body, t, "'")
        return t

    def t_LABEL(self, t):
        r"'[A-Za-z_][A-Za-z0-9_]*"
        return t

    def t_FLOAT(self, t):
        r"\d+\.\d+([eE][+-]?\d+)?"
        t.value = float(t.value)
        return t

    def t_INT(self, t):
        r"\d+"
        t.value = int(t.value)
        return t

    def t_PRINTLN(self, t):
        r"println!"
        return t

    def t_PRINT(self, t):
        r"print!"
        return t

    def t_STRUCT_NAME(self, t):
        r"[A-Z][A-Za-z0-9_]*(?=\s*\{\s*([A-Za-z_][A-Za-z0-9_]*\s*:(?!:)|\}))"
        # Nombre en mayúscula seguido de "{ campo:" -> literal de struct (o declaración)
        if t.value in KEYWORDS:
            t.type = KEYWORDS[t.value]
        return t

    def t_ID(self, t):
        r"[A-Za-z_][A-Za-z0-9_]*"
        if t.value == "_":
            t.type = "UNDERSCORE"
        else:
            t.type = KEYWORDS.get(t.value, "ID")
        return t

    # operadores (PLY ordena las cadenas por longitud de regex, mayor primero)
    t_DOTDOTEQ = r"\.\.="
    t_DOTDOT = r"\.\."
    t_COLONCOLON = r"::"
    t_ARROW = r"->"
    t_FATARROW = r"=>"
    t_PLUSEQ = r"\+="
    t_MINUSEQ = r"-="
    t_STAREQ = r"\*="
    t_SLASHEQ = r"/="
    t_PERCENTEQ = r"%="
    t_EQ = r"=="
    t_NE = r"!="
    t_LE = r"<="
    t_GE = r">="
    t_AND = r"&&"
    t_OR = r"\|\|"
    t_PLUS = r"\+"
    t_MINUS = r"-"
    t_STAR = r"\*"
    t_SLASH = r"/"
    t_PERCENT = r"%"
    t_LT = r"<"
    t_GT = r">"
    t_NOT = r"!"
    t_ASSIGN = r"="
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
    t_AMP = r"&"
    t_PIPE = r"\|"

    def t_error(self, t):
        rest = self.data[t.lexpos:]
        ch = t.value[0]
        if rest.startswith("/*"):
            self._err("Comentario de bloque sin cerrar.", t)
            t.lexer.lineno += rest.count("\n")
            t.lexer.skip(len(rest))
        elif ch == '"':
            self._err("Cadena de texto sin cerrar.", t)
            t.lexer.skip(len(rest.split("\n", 1)[0]))
        elif rest.startswith("r#\"") or rest.startswith('r"'):
            self._err("Cadena raw sin cerrar.", t)
            t.lexer.skip(len(rest))
        elif ch == "'":
            self._err("Literal de carácter mal formado.", t)
            t.lexer.skip(1)
        else:
            self._err(f"Carácter no reconocido '{ch}'.", t)
            t.lexer.skip(1)
