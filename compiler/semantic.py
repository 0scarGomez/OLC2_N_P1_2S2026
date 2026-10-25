"""Análisis semántico de OxigenNative."""

from . import ast_nodes as A
from . import typesys as T
from .symbols import FuncSym, Symbol, SymbolTable

INT_MAX = 2147483647

NUMERIC = (T.I32, T.F64)


# ---------------------------------------------------------------------------
# Reglas de tipos de operadores (tablas de la especificación)
# ---------------------------------------------------------------------------
def arithmetic_result(op, a, b):
    """Tipo resultante de a <op> b o None si la combinación es inválida."""
    if a.is_numeric and b.is_numeric:
        return T.F64 if (a.is_float or b.is_float) else T.I32
    if op == "+" and a == T.STRING and b == T.STRING:
        return T.STRING
    if op == "*" and ((a == T.STRING and b == T.I32) or (a == T.I32 and b == T.STRING)):
        return T.STRING
    return None


def relational_ok(op, a, b):
    """¿Es válida la comparación a <op> b?"""
    if a.is_numeric and b.is_numeric:
        return True
    if (a == T.I32 and b == T.CHAR) or (a == T.CHAR and b == T.I32):
        return True
    return a == b and a.kind in ("bool", "char", "String")


# ---------------------------------------------------------------------------
def unparse(n):
    """Reconstruye una representación textual de una expresión (para reportes)."""
    if isinstance(n, A.Literal):
        if n.kind == "String":
            return '"' + n.value.replace("\n", "\\n") + '"'
        if n.kind == "char":
            return "'" + n.value.replace("\n", "\\n") + "'"
        if n.kind == "bool":
            return "true" if n.value else "false"
        return repr(n.value)
    if isinstance(n, A.Identifier):
        return n.name
    if isinstance(n, A.Binary):
        return f"{unparse(n.left)} {n.op} {unparse(n.right)}"
    if isinstance(n, A.Unary):
        return f"{n.op}{unparse(n.operand)}"
    if isinstance(n, A.Cast):
        return f"{unparse(n.expr)} as {n.target}"
    if isinstance(n, A.Call):
        return f"{n.name}({', '.join(unparse(a) for a in n.args)})"
    if isinstance(n, A.MethodCall):
        return f"{unparse(n.obj)}.{n.name}({', '.join(unparse(a) for a in n.args)})"
    if isinstance(n, A.StaticCall):
        return f"{n.owner}::{n.name}({', '.join(unparse(a) for a in n.args)})"
    if isinstance(n, A.Index):
        return f"{unparse(n.base)}[{unparse(n.index)}]"
    if isinstance(n, A.Range):
        return f"{unparse(n.lo)}{'..=' if n.inclusive else '..'}{unparse(n.hi)}"
    if isinstance(n, A.SliceExpr):
        return f"&{unparse(n.base)}[{unparse(n.lo_node)}..{unparse(n.hi_node)}]"
    if isinstance(n, A.ArrayLit):
        return "[" + ", ".join(unparse(e) for e in n.elems) + "]"
    if isinstance(n, A.ArrayRepeat):
        return f"[{unparse(n.elem)}; {n.count}]"
    if isinstance(n, A.FieldAccess):
        return f"{unparse(n.base)}.{n.name}"
    if isinstance(n, A.StructLit):
        return f"{n.name} {{ ... }}"
    if isinstance(n, A.Println):
        return "println!(...)" if n.newline else "print!(...)"
    return "…"


def fmt_float(v):
    s = repr(float(v))
    return s


def const_value(n):
    """Valor constante (como texto) de una expresión sin efectos, o None."""
    try:
        v = _fold(n)
    except Exception:
        return None
    if v is None:
        return None
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return '"' + v + '"'
    if isinstance(v, float):
        return fmt_float(v)
    return str(v)


def _fold(n):
    if isinstance(n, A.Literal):
        return n.value
    if isinstance(n, A.Unary):
        v = _fold(n.operand)
        if v is None:
            return None
        if n.op == "-" and isinstance(v, (int, float)) and not isinstance(v, bool):
            return -v
        if n.op == "!" and isinstance(v, bool):
            return not v
        return None
    if isinstance(n, A.Binary) and n.type is not None and not n.type.is_none:
        a, b = _fold(n.left), _fold(n.right)
        if a is None or b is None:
            return None
        op = n.op
        if isinstance(a, str) or isinstance(b, str):
            if op == "+" and isinstance(a, str) and isinstance(b, str):
                return a + b
            return None
        if op == "+": r = a + b
        elif op == "-": r = a - b
        elif op == "*": r = a * b
        elif op == "/":
            if isinstance(a, int) and isinstance(b, int):
                if b == 0:
                    return None
                q = abs(a) // abs(b)
                r = q if (a >= 0) == (b >= 0) else -q
            else:
                r = a / b
        elif op == "%":
            if isinstance(a, int) and isinstance(b, int):
                if b == 0:
                    return None
                r = abs(a) % abs(b)
                r = r if a >= 0 else -r
            else:
                import math
                r = math.fmod(a, b)
        elif op in ("&&", "and"): return bool(a and b)
        elif op == "||": return bool(a or b)
        elif op == "==": return a == b
        elif op == "!=": return a != b
        elif op == "<": return a < b
        elif op == "<=": return a <= b
        elif op == ">": return a > b
        elif op == ">=": return a >= b
        else:
            return None
        if isinstance(r, int) and n.type == T.I32:
            r = ((r + 2 ** 31) % 2 ** 32) - 2 ** 31
        return r
    return None


# ---------------------------------------------------------------------------
class SemanticAnalyzer:
    def __init__(self, errors):
        self.errors = errors
        self.table = SymbolTable()
        self.cur_fn = None
        self.loops = []  # pila de etiquetas de ciclos (None = sin etiqueta)
        self.globals_init = []

    # -- utilidades -----------------------------------------------------------
    def err(self, msg, node, fatal=False):
        self.errors.semantico(msg, node.line, node.col, fatal=fatal)

    def expr(self, node, expected=None):
        if isinstance(node, (A.ArrayLit, A.ArrayRepeat)):
            t = getattr(self, "visit_" + node.__class__.__name__)(node, expected)
        else:
            t = node.accept(self)
        node.type = t
        return t

    # ======================================================================
    def check_type(self, t, node):
        """Verifica que los structs mencionados en un tipo existan."""
        if t is None:
            return t
        if t.kind == "struct":
            if t.n not in T.STRUCTS:
                self.err(f"El tipo '{t.n}' no está definido.", node)
                return T.NONE
            return t
        if t.kind in ("array", "slice", "vec"):
            e = self.check_type(t.elem, node)
            if e is not None and e.is_none:
                return T.NONE
        return t

    def declare_structs(self, program):
        T.STRUCTS.clear()
        decls = [i for i in program.items if isinstance(i, A.StructDecl)]
        seen = {}
        for d in decls:
            if d.name in seen:
                self.err(f"La estructura '{d.name}' ya fue declarada.", d)
                continue
            seen[d.name] = d
            T.STRUCTS[d.name] = []  # se completa abajo (permite auto-referencias detectables)
        for d in decls:
            if seen.get(d.name) is not d:
                continue
            names = set()
            fields = []
            for f in d.fields:
                if f.name in names:
                    self.err(f"El campo '{f.name}' está repetido en la estructura '{d.name}'.", f)
                    continue
                names.add(f.name)
                ft = self.check_type(f.ptype, f)
                if ft.kind == "struct" and ft.n == d.name:
                    self.err(f"La estructura '{d.name}' no puede contenerse a sí misma.", f)
                    ft = T.NONE
                fields.append((f.name, ft))
            T.STRUCTS[d.name] = fields
        # detecta ciclos de contención indirectos
        def reaches(a, b, vis):
            for _, ft in T.STRUCTS.get(a, []):
                if ft.kind == "struct":
                    if ft.n == b:
                        return True
                    if ft.n not in vis:
                        vis.add(ft.n)
                        if reaches(ft.n, b, vis):
                            return True
            return False
        for name, d in seen.items():
            if reaches(name, name, set()):
                self.err(f"La estructura '{name}' se contiene a sí misma de forma recursiva.", d, fatal=True)
                T.STRUCTS[name] = []
        for name, d in seen.items():
            sym = Symbol(name, "Struct", T.struct_of(name), False, "Global", d.line, d.col, "-")
            d.sym = sym
            self.table.all.append(sym)
        return seen

    def analyze(self, program):
        self.program = program
        self.declare_structs(program)
        funcs = [i for i in program.items if isinstance(i, A.Function)]
        for f in funcs:
            if f.name in self.table.funcs:
                self.err(f"La función '{f.name}' ya fue declarada.", f)
                continue
            for p in f.params:
                p.ptype = self.check_type(p.ptype, p)
            if f.ret_type is not None:
                f.ret_type = self.check_type(f.ret_type, f)
            params = [(p.name, p.ptype) for p in f.params]
            fs = FuncSym(f.name, params, f.ret_type or T.UNIT, f.line, f.col, f)
            f.sym = fs
            self.table.declare_function(fs)
        main = self.table.funcs.get("main")
        if main is None:
            self.errors.semantico("No se encontró la función 'main' (punto de entrada del programa).",
                                  1, 1, fatal=True)
        else:
            if main.params:
                self.err("La función 'main' no debe recibir parámetros.", main.node, fatal=True)
            if main.ret != T.UNIT:
                self.err("La función 'main' no debe retornar un valor.", main.node, fatal=True)

        self.table.push("Global")
        for item in program.items:
            if isinstance(item, A.VarDecl):
                self.visit_VarDecl(item, is_global=True)
                self.globals_init.append(item)
        for f in funcs:
            if f.sym is not None and f.sym.node is f:
                self.visit_Function(f)
        self.table.pop()
        return self.table

    # ======================================================================
    # Declaraciones
    # ======================================================================
    def visit_Function(self, f):
        self.cur_fn = f.sym
        self.table.push(f.name)
        seen = set()
        for p in f.params:
            if p.name in seen:
                self.err(f"El parámetro '{p.name}' está repetido en la función '{f.name}'.", p)
            seen.add(p.name)
            sym = Symbol(p.name, "Parámetro", p.ptype, False, f.name, p.line, p.col, "—")
            p.sym = sym
            self.table.declare(sym)
        if len(f.params) > 8:
            self.err(f"La función '{f.name}' excede el máximo de 8 parámetros.", f)
        self.stmts(f.body.stmts)
        if f.sym.ret != T.UNIT and not self.terminates_list(f.body.stmts):
            self.err(f"La función '{f.name}' debe retornar un valor de tipo {f.sym.ret} en todos los caminos de ejecución.", f)
        self.table.pop()
        self.cur_fn = None

    def stmts(self, stmts):
        for s in stmts:
            s.accept(self)

    def visit_Block(self, b):
        hint = getattr(b, "hint", None)
        fn = self.cur_fn.name if self.cur_fn else "Global"
        if hint in ("if", "else"):
            name = f"{hint} ({fn})"
        elif hint:
            name = hint
        else:
            name = f"bloque ({fn})"
        b.scope_name = name
        self.table.push(name)
        self.stmts(b.stmts)
        self.table.pop()

    def visit_StructDecl(self, d):
        pass

    def visit_VarDecl(self, d, is_global=False):
        ann = self.check_type(d.type_ann, d)
        d.type_ann = ann
        vtype = None
        if d.init is not None:
            t = self.expr(d.init, ann)
            if t == T.UNIT:
                self.err("No es posible usar una expresión sin valor como inicializador.", d.init)
                t = T.NONE
            if ann is not None:
                if not T.assignable(ann, t):
                    self.err(self._assign_msg(ann, t, d.init), d.init)
                vtype = ann
            else:
                vtype = t
                if isinstance(d.init, A.ArrayLit) and not d.init.elems:
                    self.err("No se puede inferir el tipo de un arreglo vacío.", d.init)
                    vtype = T.NONE
        else:
            if ann is not None:
                vtype = ann  # sin valor inicial: se usa el valor por defecto del tipo
            else:
                self.err(f"No se puede inferir el tipo de la variable '{d.name}'.", d)
                vtype = T.NONE
        scope = "Global" if is_global else self.table.current_name
        if vtype.kind == "struct":
            value = "-"
        elif d.init is not None:
            value = const_value(d.init) or unparse(d.init)
        else:
            value = T.default_value(vtype) or "—"
        sym = Symbol(d.name, "Variable", vtype, d.mutable, scope, d.name_line or d.line,
                     d.name_col or d.col, value)
        sym.is_global = is_global
        d.sym = sym
        self.table.declare(sym)

    @staticmethod
    def _assign_msg(dst, src, node=None):
        if isinstance(node, A.ArrayLit) and dst.kind == "array" and src.kind == "array" \
                and dst.elem == src.elem and dst.n != src.n:
            return f"El arreglo tiene {src.n} elementos pero el tipo declarado espera {dst.n}."
        return f"No es posible asignar un valor de tipo {src} a una variable de tipo {dst}."

    # ======================================================================
    # Sentencias
    # ======================================================================
    def visit_ExprStmt(self, s):
        self.expr(s.expr)

    def visit_Assign(self, s):
        tgt = s.target
        ttype = self.expr(tgt)
        # mutabilidad
        base = tgt
        while isinstance(base, A.Index):
            base = base.base
        root = tgt
        while isinstance(root, A.FieldAccess):
            root = root.base
        if isinstance(tgt, A.FieldAccess) and isinstance(root, A.Identifier) \
                and root.sym is not None and not root.sym.mutable:
            self.err(f"No es posible modificar el campo '{tgt.name}' porque '{root.name}' fue declarada como inmutable.", tgt)
            self.expr(s.value)
            s.ok = False
            return
        if isinstance(tgt, A.Identifier) and tgt.sym is not None and not tgt.sym.mutable:
            self.err(f"No es posible modificar la variable '{tgt.name}' porque fue declarada como inmutable.", tgt)
            self.expr(s.value)
            s.ok = False
            return
        vtype = self.expr(s.value, ttype)
        if ttype.is_none or vtype.is_none:
            s.ok = False
            return
        if vtype == T.UNIT:
            self.err("No es posible asignar una expresión sin valor.", s.value)
            s.ok = False
            return
        if s.op == "=":
            if not T.assignable(ttype, vtype):
                self.err(self._assign_msg(ttype, vtype, s.value), s.value)
                s.ok = False
        else:
            op = s.op[0]
            res = arithmetic_result(op, ttype, vtype)
            if res is None or (op in "-/%" and not (ttype.is_numeric and vtype.is_numeric)):
                self.err(f"No es posible aplicar el operador '{s.op}' entre los tipos {ttype} y {vtype}.", s)
                s.ok = False
            elif not T.assignable(ttype, res):
                self.err(f"No es posible asignar un valor de tipo {res} a una variable de tipo {ttype}.", s.value)
                s.ok = False
            elif op in "/%" and isinstance(s.value, A.Literal) and s.value.value == 0 and vtype == T.I32:
                self.err("División entre cero.", s.value)
                s.ok = False

    def _cond(self, c):
        t = self.expr(c)
        if not t.is_none and t != T.BOOL:
            self.err(f"La condición debe ser de tipo bool, pero se encontró {t}.", c)

    def visit_If(self, s):
        self._cond(s.cond)
        s.then.hint = "if"
        s.then.accept(self)
        if s.else_ is not None:
            if isinstance(s.else_, A.Block):
                s.else_.hint = "else"
            s.else_.accept(self)

    def visit_While(self, s):
        self._cond(s.cond)
        self.loops.append(s.label)
        s.body.hint = "while"
        s.body.accept(self)
        self.loops.pop()

    def visit_Loop(self, s):
        self.loops.append(s.label)
        s.body.hint = "loop"
        s.body.accept(self)
        self.loops.pop()

    def visit_For(self, s):
        it = s.iterable
        if isinstance(it, A.Range):
            lt = self.expr(it.lo)
            ht = self.expr(it.hi)
            it.type = T.I32
            for t, n in ((lt, it.lo), (ht, it.hi)):
                if not t.is_none and t != T.I32:
                    self.err(f"Los límites de un rango deben ser de tipo i32, pero se encontró {t}.", n)
            vt = T.I32
        else:
            t = self.expr(it)
            if t.is_seq:
                vt = t.elem
            else:
                if not t.is_none:
                    self.err(f"No es posible iterar sobre un valor de tipo {t}.", it)
                vt = T.NONE
        self.table.push("for")
        sym = Symbol(s.var, "Variable", vt, False, self.table.current_name, s.line, s.col, "—")
        s.sym = sym
        self.table.declare(sym)
        self.loops.append(s.label)
        self.stmts(s.body.stmts)
        self.loops.pop()
        self.table.pop()

    def visit_Match(self, s):
        st = self.expr(s.subject)
        if not st.is_none and st.kind not in ("i32", "char", "bool", "String"):
            self.err(f"No es posible usar 'match' sobre un valor de tipo {st}.", s.subject)
        has_wild = False
        for arm in s.arms:
            for pat in arm.patterns:
                if isinstance(pat, A.Wildcard):
                    has_wild = True
                    continue
                if isinstance(pat, A.Range):
                    lt, ht = self.expr(pat.lo), self.expr(pat.hi)
                    pat.type = T.BOOL
                    ok = all(isinstance(x, (A.Literal, A.Unary)) for x in (pat.lo, pat.hi))
                    if not ok or not (lt in (T.I32, T.CHAR) and lt == ht):
                        self.err("Los rangos de un patrón deben ser literales i32 o char del mismo tipo.", pat)
                    elif not st.is_none and st != lt:
                        self.err(f"El patrón de tipo {lt} no coincide con el valor evaluado de tipo {st}.", pat)
                    continue
                pt = self.expr(pat)
                lit_ok = isinstance(pat, A.Literal) or (
                    isinstance(pat, A.Unary) and isinstance(pat.operand, A.Literal))
                if not lit_ok:
                    self.err("Los patrones de 'match' deben ser valores literales o '_'.", pat)
                elif not st.is_none and not pt.is_none and not relational_ok("==", st, pt):
                    self.err(f"El patrón de tipo {pt} no coincide con el valor evaluado de tipo {st}.", pat)
            arm.body.accept(self)
        if not has_wild:
            self.err("La sentencia 'match' debe incluir un patrón comodín '_'.", s)

    def visit_Break(self, s):
        self._loop_target(s, "break")

    def visit_Continue(self, s):
        self._loop_target(s, "continue")

    def _loop_target(self, s, what):
        if not self.loops:
            self.err(f"'{what}' sólo puede usarse dentro de un ciclo.", s)
        elif s.label is not None and s.label not in self.loops:
            self.err(f"La etiqueta {s.label} no corresponde a ningún ciclo envolvente.", s)

    def visit_Return(self, s):
        fn = self.cur_fn
        if fn is None:
            self.err("'return' sólo puede usarse dentro de una función.", s)
            return
        if s.value is None:
            if fn.ret != T.UNIT:
                self.err(f"La función '{fn.name}' debe retornar un valor de tipo {fn.ret}.", s)
        else:
            t = self.expr(s.value, fn.ret)
            if fn.ret == T.UNIT:
                self.err(f"La función '{fn.name}' no retorna ningún valor.", s)
            elif not T.assignable(fn.ret, t):
                self.err(f"No es posible retornar un valor de tipo {t} en una función que retorna {fn.ret}.", s.value)

    # ---- análisis de flujo (¿todos los caminos retornan?) --------------------
    def terminates_list(self, stmts):
        return any(self.terminates(s) for s in stmts)

    def terminates(self, s):
        if isinstance(s, A.Return):
            return True
        if isinstance(s, A.Block):
            return self.terminates_list(s.stmts)
        if isinstance(s, A.If):
            if s.else_ is None:
                return False
            return self.terminates(s.then) and self.terminates(s.else_)
        if isinstance(s, A.Loop):
            return not self._has_break(s.body.stmts, s.label, 0)
        if isinstance(s, A.Match):
            wild = any(isinstance(p, A.Wildcard) for a in s.arms for p in a.patterns)
            return wild and all(self.terminates(a.body) for a in s.arms)
        return False

    def _has_break(self, stmts, label, depth):
        for s in stmts:
            if isinstance(s, A.Break):
                if s.label is None and depth == 0:
                    return True
                if s.label is not None and s.label == label:
                    return True
            elif isinstance(s, A.Block):
                if self._has_break(s.stmts, label, depth):
                    return True
            elif isinstance(s, A.If):
                if self._has_break(s.then.stmts, label, depth):
                    return True
                if s.else_ is not None:
                    e = s.else_
                    if self._has_break(e.stmts if isinstance(e, A.Block) else [e], label, depth):
                        return True
            elif isinstance(s, A.Match):
                for a in s.arms:
                    if self._has_break(a.body.stmts, label, depth):
                        return True
            elif isinstance(s, (A.Loop, A.While, A.For)):
                if self._has_break(s.body.stmts, label, depth + 1):
                    return True
        return False

    # ======================================================================
    # Expresiones
    # ======================================================================
    def visit_Literal(self, e):
        if e.kind == "i32" and e.value > INT_MAX + (1 if getattr(e, "neg_ok", False) else 0):
            self.err(f"El literal entero {e.value} está fuera del rango de i32.", e)
        return {"i32": T.I32, "f64": T.F64, "bool": T.BOOL, "char": T.CHAR, "String": T.STRING}[e.kind]

    def visit_Identifier(self, e):
        sym = self.table.lookup(e.name)
        if sym is None:
            if e.name in self.table.funcs:
                self.err(f"'{e.name}' es una función; use '{e.name}(...)' para invocarla.", e)
            else:
                self.err(f"La variable '{e.name}' no ha sido declarada.", e)
            return T.NONE
        e.sym = sym
        return sym.type

    def visit_Unary(self, e):
        if e.op == "-" and isinstance(e.operand, A.Literal):
            e.operand.neg_ok = True
        t = self.expr(e.operand)
        if t.is_none:
            return T.NONE
        if e.op == "-":
            if t.is_numeric:
                return t
        elif t == T.BOOL:
            return T.BOOL
        self.err(f"No es posible aplicar el operador '{e.op}' al tipo {t}.", e)
        return T.NONE

    def visit_Binary(self, e):
        lt = self.expr(e.left)
        rt = self.expr(e.right)
        op = e.op
        pos = A.Node()
        pos.line, pos.col = e.op_line, e.op_col
        if lt.is_none or rt.is_none:
            return T.NONE
        if op in ("&&", "||"):
            if lt == T.BOOL and rt == T.BOOL:
                return T.BOOL
        elif op in ("+", "-", "*", "/", "%"):
            res = arithmetic_result(op, lt, rt)
            if res is not None and (op in "+*" or (lt.is_numeric and rt.is_numeric)):
                if op in "/%" and isinstance(e.right, A.Literal) and e.right.kind == "i32" and e.right.value == 0:
                    self.err("División entre cero.", e.right)
                    return T.NONE
                return res
        else:
            if relational_ok(op, lt, rt):
                return T.BOOL
        self.err(f"No es posible aplicar el operador '{op}' entre los tipos {lt} y {rt}.", pos)
        return T.NONE

    def visit_Cast(self, e):
        t = self.expr(e.expr)
        dst = e.target
        if t.is_none:
            return dst
        ok = ((t.is_numeric and dst.is_numeric) or (t == T.CHAR and dst == T.I32)
              or (t == T.I32 and dst == T.CHAR) or (t == T.BOOL and dst == T.I32) or t == dst)
        if not ok:
            self.err(f"No es posible convertir un valor de tipo {t} a {dst}.", e)
            return T.NONE
        return dst

    # ---- llamadas ----------------------------------------------------------------
    def visit_Call(self, e):
        name = e.name
        if name == "typeof":
            if len(e.args) != 1:
                self.err(f"La función 'typeof' esperaba 1 argumento, pero recibió {len(e.args)}.", e)
                for a in e.args:
                    self.expr(a)
                return T.NONE
            t = self.expr(e.args[0])
            e.func = "typeof"
            e.static_str = str(t) if not t.is_none else "None"
            return T.STRING
        if name == "random":
            ts = [self.expr(a) for a in e.args]
            if len(e.args) != 2:
                self.err(f"La función 'random' esperaba 2 argumentos, pero recibió {len(e.args)}.", e)
                return T.NONE
            for t, a in zip(ts, e.args):
                if not t.is_none and t != T.I32:
                    self.err(f"Los argumentos de 'random' deben ser de tipo i32, pero se encontró {t}.", a)
            e.func = "random"
            return T.I32
        fs = self.table.funcs.get(name)
        if fs is None:
            for a in e.args:
                self.expr(a)
            self.err(f"La función '{name}' no ha sido declarada.", e)
            return T.NONE
        e.func = fs
        if len(e.args) != len(fs.params):
            for a in e.args:
                self.expr(a)
            self.err(f"La función '{name}' esperaba {len(fs.params)} argumentos, pero recibió {len(e.args)}.", e)
            e.func = None
            return fs.ret
        bad = False
        for i, (a, (pn, pt)) in enumerate(zip(e.args, fs.params)):
            at = self.expr(a, pt)
            if not T.assignable(pt, at):
                self.err(f"Tipos incompatibles. No es posible utilizar un valor de tipo {at} donde se esperaba un valor de tipo {pt} (argumento '{pn}' de '{name}').", a)
                bad = True
        if bad:
            e.func = None
        return fs.ret

    def visit_StaticCall(self, e):
        ts = [self.expr(a) for a in e.args]
        if e.name == "from":
            if len(e.args) != 1:
                self.err(f"String::from esperaba 1 argumento, pero recibió {len(e.args)}.", e)
                return T.NONE
            if not ts[0].is_none and ts[0] != T.STRING:
                self.err(f"String::from esperaba una cadena, pero recibió un valor de tipo {ts[0]}.", e.args[0])
                return T.NONE
            return T.STRING
        if e.name == "new":
            if e.args:
                self.err(f"String::new no recibe argumentos.", e)
            return T.STRING
        self.err(f"El tipo String no tiene la función asociada '{e.name}'.", e)
        return T.NONE

    def _mut_target(self, obj, what):
        """El receptor de un método que modifica debe ser una variable mutable."""
        base = obj
        while isinstance(base, A.Index):
            base = base.base
        if isinstance(base, A.Identifier) and base.sym is not None and not base.sym.mutable:
            self.err(f"No es posible modificar la variable '{base.name}' con '{what}' porque fue declarada como inmutable.", obj)
            return False
        return True

    def visit_MethodCall(self, e):
        ot = self.expr(e.obj)
        ats = [self.expr(a) for a in e.args]
        name = e.name
        e.method_pos = (getattr(e, "name_line", e.line), getattr(e, "name_col", e.col))

        def argc(n):
            if len(e.args) != n:
                self.err(f"El método '{name}' esperaba {n} argumentos, pero recibió {len(e.args)}.", e)
                return False
            return True

        if ot.is_none:
            return T.NONE
        if name == "len":
            if ot == T.STRING or ot.is_seq:
                return T.I32 if argc(0) else T.NONE
        elif name == "contains":
            if argc(1):
                if ot == T.STRING:
                    if ats[0] == T.STRING:
                        return T.BOOL
                    if not ats[0].is_none:
                        self.err(f"contains esperaba un String, pero recibió {ats[0]}.", e.args[0])
                    return T.NONE
                if ot.is_seq:
                    if ats[0].is_none:
                        return T.NONE
                    if relational_ok("==", ot.elem, ats[0]) and not ot.elem.is_seq:
                        return T.BOOL
                    self.err(f"contains esperaba un valor de tipo {ot.elem}, pero recibió {ats[0]}.", e.args[0])
                    return T.NONE
            else:
                return T.NONE
        elif name == "replace" and ot == T.STRING:
            if argc(2):
                if all(a == T.STRING or a.is_none for a in ats):
                    return T.STRING
                self.err("replace esperaba dos argumentos de tipo String.", e)
            return T.NONE
        elif name == "split" and ot == T.STRING:
            if argc(1):
                if ats[0] == T.STRING or ats[0].is_none:
                    return T.vec_of(T.STRING)
                self.err(f"split esperaba un String, pero recibió {ats[0]}.", e.args[0])
            return T.NONE
        elif name == "split_whitespace" and ot == T.STRING:
            return T.vec_of(T.STRING) if argc(0) else T.NONE
        elif name == "collect" and ot.kind == "vec":
            return ot if argc(0) else T.NONE
        elif name in ("to_uppercase", "to_lowercase") and ot == T.STRING:
            return T.STRING if argc(0) else T.NONE
        elif name == "push_str" and ot == T.STRING:
            if argc(1):
                if ats[0] != T.STRING and not ats[0].is_none:
                    self.err(f"push_str esperaba un String, pero recibió {ats[0]}.", e.args[0])
                    return T.NONE
                if not isinstance(e.obj, (A.Identifier, A.Index)):
                    self.err("push_str sólo puede aplicarse a una variable.", e)
                    return T.NONE
                if not self._mut_target(e.obj, "push_str"):
                    return T.NONE
                return T.UNIT
            return T.NONE
        elif name == "reverse" and ot.is_seq:
            if argc(0):
                if ot.kind == "slice" or self._mut_target(e.obj, "reverse"):
                    return T.UNIT
            return T.NONE
        self.err(f"El tipo {ot} no tiene un método '{name}' con esos argumentos.", e)
        return T.NONE

    # ---- structs -----------------------------------------------------------------
    def visit_StructLit(self, e):
        fields = T.STRUCTS.get(e.name)
        if fields is None:
            self.err(f"La estructura '{e.name}' no está definida.", e)
            for _, v, _, _ in e.inits:
                self.expr(v)
            return T.NONE
        e.struct_type = T.struct_of(e.name)
        ftypes = dict(fields)
        given = set()
        for fname, val, ln, cl in e.inits:
            ft = ftypes.get(fname)
            if ft is None:
                self.errors.semantico(f"La estructura '{e.name}' no tiene un campo llamado '{fname}'.", ln, cl)
                self.expr(val)
                continue
            if fname in given:
                self.errors.semantico(f"El campo '{fname}' se inicializa más de una vez.", ln, cl)
            given.add(fname)
            vt = self.expr(val, ft)
            if not vt.is_none and not ft.is_none and not T.assignable(ft, vt):
                self.err(f"No es posible asignar un valor de tipo {vt} al campo '{fname}' de tipo {ft}.", val)
        missing = [n for n, _ in fields if n not in given]
        if missing:
            self.err("Faltan campos en la inicialización de '" + e.name + "': " + ", ".join(missing) + ".", e)
        return e.struct_type

    def visit_FieldAccess(self, e):
        bt = self.expr(e.base)
        if bt.is_none:
            return T.NONE
        if bt.kind != "struct":
            self.errors.semantico(f"No es posible acceder al campo '{e.name}' de un valor de tipo {bt}.",
                                  e.name_line or e.line, e.name_col or e.col)
            return T.NONE
        r = bt.field_offset(e.name)
        if r is None:
            self.errors.semantico(f"La estructura '{bt.n}' no tiene un campo llamado '{e.name}'.",
                                  e.name_line or e.line, e.name_col or e.col)
            return T.NONE
        e.offset = r[0]
        return r[1]

    # ---- arreglos ----------------------------------------------------------------
    def visit_Index(self, e):
        bt = self.expr(e.base)
        if isinstance(e.index, A.Range):
            self.err("Un rango sólo puede usarse como slice con '&' (por ejemplo &arr[1..3]).", e.index)
            return T.NONE
        it = self.expr(e.index)
        if bt.is_none:
            return T.NONE
        if not bt.is_seq:
            self.err(f"No es posible indexar un valor de tipo {bt}.", e)
            return T.NONE
        if not it.is_none and it != T.I32:
            self.err(f"El índice de un arreglo debe ser de tipo i32, pero se encontró {it}.", e.index)
            return T.NONE
        if bt.kind in ("array", "slice") and isinstance(e.index, A.Literal):
            if e.index.value >= bt.n:
                self.err("Índice fuera de los límites del arreglo.", e)
                return T.NONE
        elif bt.kind in ("array", "slice") and isinstance(e.index, A.Unary) and \
                e.index.op == "-" and isinstance(e.index.operand, A.Literal):
            self.err("Índice fuera de los límites del arreglo.", e)
            return T.NONE
        return bt.elem

    def visit_Range(self, e):
        self.err("Un rango sólo puede usarse en 'for', en 'match' o como slice.", e)
        return T.NONE

    def visit_SliceExpr(self, e):
        bt = self.expr(e.base)
        lt = self.expr(e.lo_node)
        ht = self.expr(e.hi_node)
        if bt.is_none or lt.is_none or ht.is_none:
            return T.NONE
        if not bt.is_seq:
            self.err(f"No es posible crear un slice de un valor de tipo {bt}.", e)
            return T.NONE
        if not (isinstance(e.lo_node, A.Literal) and isinstance(e.hi_node, A.Literal)
                and e.lo_node.kind == "i32" and e.hi_node.kind == "i32"):
            self.err("Los límites de un slice deben ser literales enteros.", e)
            return T.NONE
        lo, hi = e.lo_node.value, e.hi_node.value
        if getattr(e, "inclusive", False):
            hi += 1
        e.lo, e.hi = lo, hi
        if lo > hi:
            self.err("El inicio del slice es mayor que su final.", e)
            return T.NONE
        if bt.kind in ("array", "slice") and hi > bt.n:
            self.err("Slice fuera de los límites del arreglo.", e)
            return T.NONE
        return T.slice_of(bt.elem, hi - lo)

    def visit_ArrayLit(self, e, expected=None):
        exp_elem = expected.elem if expected is not None and expected.kind in ("array", "vec") else None
        if not e.elems:
            return T.array_of(exp_elem or T.NONE, 0)
        types = [self.expr(x, exp_elem) for x in e.elems]
        base = exp_elem
        if base is None:
            base = next((t for t in types if not t.is_none), T.NONE)
        for t, x in zip(types, e.elems):
            if t.is_none or base.is_none:
                continue
            if not T.assignable(base, t):
                self.err(f"Los elementos de un arreglo deben tener el mismo tipo: se esperaba {base}, pero se encontró {t}.", x)
        return T.array_of(base, len(e.elems))

    def visit_ArrayRepeat(self, e, expected=None):
        exp_elem = expected.elem if expected is not None and expected.kind == "array" else None
        t = self.expr(e.elem, exp_elem)
        if exp_elem is not None and not t.is_none and T.assignable(exp_elem, t):
            t = exp_elem
        return T.array_of(t, e.count)

    # ---- println! ------------------------------------------------------------------
    def visit_Println(self, e):
        name = "println!" if e.newline else "print!"
        e.fmt = None
        if not e.args:
            e.fmt = []
            return T.UNIT
        first = e.args[0]
        if isinstance(first, A.Literal) and first.kind == "String":
            first.type = T.STRING
            segs, placeholders = self._parse_format(first.value, first)
            args = e.args[1:]
            types = [self.expr(a) for a in args]
            if len(args) != placeholders:
                self.err(f"La cadena de formato espera {placeholders} argumento(s), pero se recibieron {len(args)}.", first)
            for t, a in zip(types, args):
                if t == T.UNIT:
                    self.err(f"No es posible imprimir una expresión sin valor ({name}).", a)
            e.fmt = segs
        else:
            if len(e.args) > 1:
                self.err(f"El primer argumento de {name} debe ser una cadena de formato literal.", first)
            for a in e.args:
                t = self.expr(a)
                if t == T.UNIT:
                    self.err(f"No es posible imprimir una expresión sin valor ({name}).", a)
            e.fmt = [("value", False, None)]
            e.args = [first]
        return T.UNIT

    def _parse_format(self, s, node):
        segs, buf, i, n, count = [], "", 0, len(s), 0
        while i < n:
            c = s[i]
            if c == "{":
                if i + 1 < n and s[i + 1] == "{":
                    buf += "{"
                    i += 2
                    continue
                j = s.find("}", i)
                if j < 0:
                    self.err("Cadena de formato inválida: falta '}'.", node)
                    break
                spec = s[i + 1:j]
                if buf:
                    segs.append(("text", buf))
                    buf = ""
                debug, prec = False, None
                if spec == "":
                    pass
                elif spec in (":?", ":#?"):
                    debug = True
                elif spec.startswith(":.") and spec[2:].isdigit():
                    prec = int(spec[2:])
                else:
                    self.err(f"Especificador de formato no soportado '{{{spec}}}'.", node)
                segs.append(("arg", debug, prec))
                count += 1
                i = j + 1
                continue
            if c == "}":
                if i + 1 < n and s[i + 1] == "}":
                    buf += "}"
                    i += 2
                    continue
                self.err("Cadena de formato inválida: '}' sin su '{'.", node)
                i += 1
                continue
            buf += c
            i += 1
        if buf:
            segs.append(("text", buf))
        return segs, count
