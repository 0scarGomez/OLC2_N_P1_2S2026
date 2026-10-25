"""Tabla de símbolos con ámbitos anidados."""


class Symbol:
    """Variable, parámetro o función registrada durante el análisis semántico."""

    def __init__(self, name, category, type_, mutable, scope, line, col, value="—"):
        self.name = name
        self.category = category  # Variable | Parámetro | Función
        self.type = type_
        self.mutable = mutable
        self.scope = scope  # nombre del ámbito donde se declaró
        self.line = line
        self.col = col
        self.value = value
        self.is_global = False
        # usados por la generación de código
        self.slot = None
        self.label = None

    def to_dict(self, number):
        return {
            "no": number,
            "identificador": self.name,
            "categoria": self.category,
            "tipo": str(self.type),
            "ambito": self.scope,
            "linea": self.line,
            "columna": self.col,
            "mutable": "mut" if self.mutable else "",
            "valor": self.value,
        }


class FuncSym:
    def __init__(self, name, params, ret, line, col, node=None):
        self.name = name
        self.params = params  # lista de (nombre, Type)
        self.ret = ret
        self.line = line
        self.col = col
        self.node = node
        self.label = "main" if name == "main" else f"fn_{name}"


class SymbolTable:
    def __init__(self):
        self.scopes = []
        self.names = []
        self.all = []  # historial completo (para el reporte)
        self.funcs = {}
        self._counter = 0

    # -- ámbitos --------------------------------------------------------------
    def push(self, name):
        self.scopes.append({})
        self.names.append(name)

    def pop(self):
        self.scopes.pop()
        self.names.pop()

    @property
    def current_name(self):
        return self.names[-1] if self.names else "Global"

    def new_block_name(self):
        self._counter += 1
        return f"{self.current_name} › bloque {self._counter}"

    # -- símbolos ---------------------------------------------------------------
    def declare(self, sym):
        self.scopes[-1][sym.name] = sym  # permite sombreado (shadowing)
        self.all.append(sym)
        return sym

    def lookup(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def declare_function(self, fsym):
        self.funcs[fsym.name] = fsym
        self.all.append(fsym)

    def report_rows(self):
        rows = []
        for i, s in enumerate(self.all):
            if isinstance(s, FuncSym):
                rows.append({
                    "no": i + 1, "identificador": s.name, "categoria": "Función",
                    "tipo": str(s.ret), "ambito": "Global", "linea": s.line,
                    "columna": s.col, "mutable": "",
                    "valor": "(" + ", ".join(f"{n}: {t}" for n, t in s.params) + ")",
                })
            else:
                rows.append(s.to_dict(i + 1))
        return rows
