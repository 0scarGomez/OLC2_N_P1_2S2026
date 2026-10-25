"""Nodos propios del Árbol de Sintaxis Abstracta (AST) de OxigenNative.

PLY no construye un AST automáticamente: cada regla del parser instancia
estas clases. Cada nodo conoce sus hijos (para el reporte Graphviz) y es
anotado por el análisis semántico con `.type` (tipo estático resultante).
"""


class Node:
    fields = ()
    title = None          # etiqueta para el reporte AST

    def __init__(self, *args, pos=None):
        if len(args) != len(self.fields):
            raise TypeError(f"{type(self).__name__} espera {len(self.fields)} argumentos")
        for name, value in zip(self.fields, args):
            setattr(self, name, value)
        self.pos = pos or (0, 0)
        self.type = None

    # -- navegación ----------------------------------------------------------
    def children(self):
        out = []
        for f in self.fields:
            v = getattr(self, f)
            if isinstance(v, Node):
                out.append(v)
            elif isinstance(v, (list, tuple)):
                out.extend(x for x in v if isinstance(x, Node))
        return out

    def dot_label(self):
        return self.title or type(self).__name__

    def dot_children(self):
        return self.children()


class Leaf:
    """Hoja sintética para el reporte (no forma parte del AST ejecutable)."""

    def __init__(self, label):
        self.label = label

    def dot_label(self):
        return self.label

    def dot_children(self):
        return []


# ------------------------------------------------------------------ programa
class Program(Node):
    fields = ("functions",)
    title = "Program"


class Param(Node):
    fields = ("name", "ptype")

    def dot_label(self):
        return f"Param\n{self.name}: {self.ptype}"


class FunctionDecl(Node):
    fields = ("name", "params", "ret", "body")

    def dot_label(self):
        ret = f" -> {self.ret}" if self.ret else ""
        return f"Function\n{self.name}{ret}"

    def dot_children(self):
        return list(self.params) + [self.body]


class Block(Node):
    fields = ("stmts",)
    title = "Block"


# ------------------------------------------------------------------ sentencias
class VarDecl(Node):
    fields = ("name", "mutable", "ptype", "init")

    def dot_label(self):
        return "VariableDeclaration\n" + ("let mut" if self.mutable else "let")

    def dot_children(self):
        kids = [Leaf(f"Identifier\n{self.name}")]
        if self.ptype is not None:
            kids.append(Leaf(f"Type\n{self.ptype}"))
        if self.init is not None:
            kids.append(self.init)
        return kids


class Assign(Node):
    fields = ("target", "op", "value")

    def dot_label(self):
        return f"Assignment\n{self.op}"


class ExprStmt(Node):
    fields = ("expr",)
    title = "ExpressionStatement"


class Println(Node):
    fields = ("args", "newline")

    def dot_label(self):
        return "Println" if self.newline else "Print"


class If(Node):
    fields = ("cond", "then", "orelse")
    title = "If"

    def dot_children(self):
        kids = [self.cond, self.then]
        if self.orelse is not None:
            kids.append(self.orelse)
        return kids


class While(Node):
    fields = ("label", "cond", "body")

    def dot_label(self):
        return "While" + (f"\n{self.label}" if self.label else "")


class Loop(Node):
    fields = ("label", "body")

    def dot_label(self):
        return "Loop" + (f"\n{self.label}" if self.label else "")


class Match(Node):
    fields = ("expr", "arms")
    title = "Match"


class MatchArm(Node):
    fields = ("patterns", "body")

    def dot_label(self):
        return "Arm"

    def dot_children(self):
        return list(self.patterns) + [self.body]


class Break(Node):
    fields = ("label",)

    def dot_label(self):
        return "Break" + (f"\n{self.label}" if self.label else "")


class Continue(Node):
    fields = ("label",)

    def dot_label(self):
        return "Continue" + (f"\n{self.label}" if self.label else "")


class Return(Node):
    fields = ("expr",)
    title = "Return"


# ------------------------------------------------------------------ expresiones
class IntLit(Node):
    fields = ("value",)

    def dot_label(self):
        return f"Literal\n{self.value}"


class FloatLit(Node):
    fields = ("value",)

    def dot_label(self):
        return f"Literal\n{self.value}"


class BoolLit(Node):
    fields = ("value",)

    def dot_label(self):
        return f"Literal\n{'true' if self.value else 'false'}"


class CharLit(Node):
    fields = ("value",)

    def dot_label(self):
        return f"Literal\n'{self.value}'".replace("\n'\n'", "\n'\\n'")


class StrLit(Node):
    fields = ("value",)

    def dot_label(self):
        shown = self.value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'Literal\n"{shown}"'


class Identifier(Node):
    fields = ("name",)

    def dot_label(self):
        return f"Identifier\n{self.name}"


class Binary(Node):
    fields = ("op", "left", "right")

    def dot_label(self):
        return f"Binary\n{self.op}"


class Unary(Node):
    fields = ("op", "operand")

    def dot_label(self):
        return f"Unary\n{self.op}"


class Call(Node):
    fields = ("name", "args")

    def dot_label(self):
        return f"Call\n{self.name}"


class MethodCall(Node):
    fields = ("obj", "name", "args")

    def dot_label(self):
        return f"MethodCall\n{self.name}"

    def dot_children(self):
        return [self.obj] + list(self.args)


class Index(Node):
    fields = ("base", "index")
    title = "Index"


class Slice(Node):
    fields = ("base", "lo", "hi")
    title = "Slice"

    def dot_label(self):
        return f"Slice\n[{self.lo}..{self.hi}]"

    def dot_children(self):
        return [self.base]


class ArrayLit(Node):
    fields = ("elems",)
    title = "ArrayLiteral"


class ArrayRepeat(Node):
    fields = ("value", "count")

    def dot_label(self):
        return f"ArrayRepeat\n;{self.count}"

    def dot_children(self):
        return [self.value]


class StringFrom(Node):
    fields = ("arg",)
    title = "String::from"


class StringNew(Node):
    fields = ()
    title = "String::new"


class Wildcard(Node):
    """Patrón comodín `_` de una sentencia match."""
    fields = ()
    title = "_"
