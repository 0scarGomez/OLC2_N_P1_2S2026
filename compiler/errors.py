"""Manejo de errores del compilador"""

LEXICO = "Léxico"
SINTACTICO = "Sintáctico"
SEMANTICO = "Semántico"


class CompileError:
    def __init__(self, kind, message, line, col, snippet=""):
        self.kind = kind
        self.message = message
        self.line = line
        self.col = col
        self.snippet = snippet

    def format(self):
        return f"[Error {self.kind}] Línea {self.line}, Columna {self.col}\n{self.message}"

    def to_dict(self, number):
        return {
            "no": number,
            "tipo": self.kind,
            "descripcion": self.message,
            "linea": self.line,
            "columna": self.col,
            "fragmento": self.snippet,
        }

    def __repr__(self):
        return f"<{self.kind} {self.line}:{self.col} {self.message}>"


class ErrorList:
    """Colección ordenada de errores de una compilación."""

    def __init__(self, source=""):
        self.items = []
        self.lines = source.split("\n")
        self.fatal = False  # errores que impiden generar/ejecutar código
        self._seen = set()

    def add(self, kind, message, line, col, fatal=False):
        key = (kind, message, line, col)
        if key in self._seen:
            return
        self._seen.add(key)
        snippet = ""
        if 1 <= line <= len(self.lines):
            snippet = self.lines[line - 1].strip()
        self.items.append(CompileError(kind, message, line, col, snippet))
        if fatal:
            self.fatal = True

    def lexico(self, message, line, col):
        self.add(LEXICO, message, line, col)

    def sintactico(self, message, line, col, fatal=True):
        self.add(SINTACTICO, message, line, col, fatal=fatal)

    def semantico(self, message, line, col, fatal=False):
        self.add(SEMANTICO, message, line, col, fatal=fatal)

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def sorted(self):
        order = {LEXICO: 0, SINTACTICO: 1, SEMANTICO: 2}
        return sorted(self.items, key=lambda e: (order[e.kind], e.line, e.col))

    def format_all(self):
        return "\n\n".join(e.format() for e in self.sorted())

    def to_list(self):
        return [e.to_dict(i + 1) for i, e in enumerate(self.sorted())]
