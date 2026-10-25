"""Nodos del Árbol de Sintaxis Abstracta (AST)"""

from dataclasses import dataclass, fields
from typing import Any, List, Optional


class Node:
    line = 0
    col = 0
    type = None  # anotado por el análisis semántico

    def accept(self, visitor):
        method = getattr(visitor, "visit_" + self.__class__.__name__, None)
        if method is None:
            raise NotImplementedError(f"{visitor.__class__.__name__} no implementa visit_{self.__class__.__name__}")
        return method(self)

    def children(self):
        out = []
        for f in fields(self):
            v = getattr(self, f.name)
            if isinstance(v, Node):
                out.append(v)
            elif isinstance(v, (list, tuple)):
                for x in v:
                    if isinstance(x, Node):
                        out.append(x)
                    elif isinstance(x, tuple) and len(x) > 1 and isinstance(x[1], Node):
                        out.append(x[1])
        return out


# ----------------------------------------------------------------------------
# Programa y declaraciones
# ----------------------------------------------------------------------------
@dataclass(eq=False)
class Program(Node):
    items: List[Node]


@dataclass(eq=False)
class Function(Node):
    name: str
    params: List["Param"]
    ret_type: Any  # Type o None
    body: "Block"
    sym: Any = None


@dataclass(eq=False)
class Param(Node):
    name: str
    ptype: Any
    sym: Any = None


@dataclass(eq=False)
class Block(Node):
    stmts: List[Node]
    scope_name: str = ""


@dataclass(eq=False)
class VarDecl(Node):
    name: str
    mutable: bool
    type_ann: Any  # Type o None
    init: Optional[Node]
    sym: Any = None
    name_line: int = 0
    name_col: int = 0


# ----------------------------------------------------------------------------
# Sentencias
# ----------------------------------------------------------------------------
@dataclass(eq=False)
class Assign(Node):
    target: Node
    op: str  # '=', '+=', '-=', '*=', '/=', '%='
    value: Node
    ok: bool = True  # False si el análisis semántico lo rechazó


@dataclass(eq=False)
class ExprStmt(Node):
    expr: Node


@dataclass(eq=False)
class If(Node):
    cond: Node
    then: "Block"
    else_: Optional[Node]  # Block | If | None


@dataclass(eq=False)
class While(Node):
    cond: Node
    body: "Block"
    label: Optional[str] = None


@dataclass(eq=False)
class Loop(Node):
    body: "Block"
    label: Optional[str] = None


@dataclass(eq=False)
class For(Node):
    var: str
    iterable: Node
    body: "Block"
    label: Optional[str] = None
    sym: Any = None


@dataclass(eq=False)
class MatchArm(Node):
    patterns: List[Node]  # nodos expresión, Wildcard o Range
    body: Node


@dataclass(eq=False)
class Match(Node):
    subject: Node
    arms: List[MatchArm]


@dataclass(eq=False)
class Wildcard(Node):
    pass


@dataclass(eq=False)
class Break(Node):
    label: Optional[str] = None


@dataclass(eq=False)
class Continue(Node):
    label: Optional[str] = None


@dataclass(eq=False)
class Return(Node):
    value: Optional[Node] = None


# ----------------------------------------------------------------------------
# Expresiones
# ----------------------------------------------------------------------------
@dataclass(eq=False)
class Literal(Node):
    kind: str  # i32 | f64 | bool | char | String
    value: Any


@dataclass(eq=False)
class Identifier(Node):
    name: str
    sym: Any = None


@dataclass(eq=False)
class Binary(Node):
    op: str
    left: Node
    right: Node
    op_line: int = 0
    op_col: int = 0


@dataclass(eq=False)
class Unary(Node):
    op: str  # '-' | '!'
    operand: Node


@dataclass(eq=False)
class Cast(Node):
    expr: Node
    target: Any


@dataclass(eq=False)
class Call(Node):
    name: str
    args: List[Node]
    func: Any = None  # FuncSym o nombre de función embebida


@dataclass(eq=False)
class MethodCall(Node):
    obj: Node
    name: str
    args: List[Node]


@dataclass(eq=False)
class StaticCall(Node):  # String::from(...), String::new()
    owner: str
    name: str
    args: List[Node]


@dataclass(eq=False)
class Index(Node):
    base: Node
    index: Node
    const_checked: bool = False


@dataclass(eq=False)
class Range(Node):
    lo: Node
    hi: Node
    inclusive: bool = False


@dataclass(eq=False)
class SliceExpr(Node):  # &arr[a..b]
    base: Node
    lo: int
    hi: int
    lo_node: Any = None
    hi_node: Any = None


@dataclass(eq=False)
class ArrayLit(Node):
    elems: List[Node]


@dataclass(eq=False)
class ArrayRepeat(Node):  # [expr; N]
    elem: Node
    count: int


@dataclass(eq=False)
class Println(Node):
    args: List[Node]
    newline: bool = True
    fmt: Any = None  # lista de segmentos tras el análisis semántico


@dataclass(eq=False)
class StructDecl(Node):
    name: str
    fields: List["Param"]  # (nombre, tipo) en orden de declaración
    sym: Any = None


@dataclass(eq=False)
class StructLit(Node):
    name: str
    inits: List[Any]  # lista de (nombre, expr, línea, columna)
    struct_type: Any = None


@dataclass(eq=False)
class FieldAccess(Node):
    base: Node
    name: str
    offset: int = 0
    name_line: int = 0
    name_col: int = 0
