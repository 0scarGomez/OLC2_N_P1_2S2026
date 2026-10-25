"""Registro de errores léxicos, sintácticos y semánticos."""

LEXICO = "Léxico"
SINTACTICO = "Sintáctico"
SEMANTICO = "Semántico"


class CompileError:
    def __init__(self, tipo, desc, line, col, fragment=""):
        self.tipo = tipo
        self.desc = desc
        self.line = line
        self.col = col
        self.fragment = fragment

    def format(self):
        return f"[Error {self.tipo}] Línea {self.line}, Columna {self.col}\n{self.desc}"

    def to_dict(self, no):
        return {"no": no, "tipo": self.tipo, "descripcion": self.desc,
                "linea": self.line, "columna": self.col, "fragmento": self.fragment}


class ErrorLog:
    def __init__(self, source=""):
        self.items = []
        self.lines = source.split("\n")
        self._seen = set()

    def add(self, tipo, desc, line, col):
        key = (tipo, desc, line, col)
        if key in self._seen:          # evita duplicados exactos
            return
        self._seen.add(key)
        frag = ""
        if 1 <= line <= len(self.lines):
            frag = self.lines[line - 1].strip()
        self.items.append(CompileError(tipo, desc, line, col, frag))

    def has(self, *tipos):
        return any(e.tipo in tipos for e in self.items)

    def __len__(self):
        return len(self.items)

    def sorted_items(self):
        return sorted(self.items, key=lambda e: (e.line, e.col))

    def to_list(self):
        return [e.to_dict(i + 1) for i, e in enumerate(self.items)]
