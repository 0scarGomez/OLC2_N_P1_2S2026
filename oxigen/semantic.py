"""Análisis semántico de OxigenNative.

Valida tipos, ámbitos, mutabilidad, arreglos, funciones y control de flujo.
Anota el AST (node.type, node.sym, node.slot, ...) para que el generador de
código ARM64 pueda traducirlo directamente, sin representación intermedia.

Los errores semánticos NO detienen el análisis: la expresión inválida toma el
tipo NONE y se continúa, de modo que se reportan múltiples errores por corrida.
"""
from . import ast_nodes as A
from . import types as T
from .errors import SEMANTICO

# Si es False, los elementos de un arreglo declarado sin `mut` pueden modificarse
# (el ejemplo de matrices de la especificación hace `matrix[1][2] = 7` sobre un `let`
# sin mut). Ponerlo en True aplica la regla estricta de Rust.
STRICT_ARRAY_MUTABILITY = False

INT_MAX_LIT = 2147483648


class Symbol:
    def __init__(self, name, category, type_, scope, line, col, mutable=False, slot=None, value=None):
        self.name = name
        self.category = category
        self.type = type_
        self.scope = scope
        self.line = line
        self.col = col
        self.mutable = mutable
        self.slot = slot
        self.value = value


class FuncInfo:
    def __init__(self, name, params, ret, decl):
        self.name = name
        self.params = params          # [(nombre, tipo)]
        self.ret = ret                # Type (UNIT si no retorna)
        self.decl = decl
        self.label = "main" if name == "main" else f"fn_{name}"


ORDERABLE = {
    (T.I32, T.I32), (T.I32, T.F64), (T.F64, T.I32), (T.F64, T.F64),
    (T.I32, T.CHAR), (T.CHAR, T.I32), (T.CHAR, T.CHAR),
    (T.BOOL, T.BOOL), (T.STRING, T.STRING),
}


def arith_result(op, lt, rt):
    """Tabla de tipos resultantes de los operadores aritméticos (sección 3.3.5)."""
    if op == "+" and lt == T.STRING and rt == T.STRING:
        return T.STRING
    if op == "*" and ((lt == T.I32 and rt == T.STRING) or (lt == T.STRING and rt == T.I32)):
        return T.STRING
    if lt in (T.I32, T.F64) and rt in (T.I32, T.F64):
        return T.F64 if T.F64 in (lt, rt) else T.I32
    return None


def literal_text(node):
    if isinstance(node, A.IntLit):
        return str(node.value)
    if isinstance(node, A.FloatLit):
        return repr(node.value)
    if isinstance(node, A.BoolLit):
        return "true" if node.value else "false"
    if isinstance(node, A.StrLit):
        return '"' + node.value.replace("\n", "\\n") + '"'
    if isinstance(node, A.CharLit):
        return "'" + node.value.replace("\n", "\\n") + "'"
    if isinstance(node, A.StringFrom) and isinstance(node.arg, A.StrLit):
        return literal_text(node.arg)
    if isinstance(node, A.Unary) and node.op == "-" and isinstance(node.operand, (A.IntLit, A.FloatLit)):
        return "-" + literal_text(node.operand)
    return "—"


class Semantic:
    def __init__(self, program, errors):
        self.program = program
        self.errors = errors
        self.funcs = {}
        self.symbols = []          # tabla de símbolos para el reporte
        self.scopes = []
        self.scope_names = []
        self.fn = None
        self.nslots = 0
        self.loops = []
        self.block_counter = 0

    # ------------------------------------------------------------------ utilidades
    def err(self, desc, pos):
        line, col = pos
        self.errors.add(SEMANTICO, desc, line, col)

    def push_scope(self, name):
        self.scopes.append({})
        self.scope_names.append(name)

    def pop_scope(self):
        self.scopes.pop()
        self.scope_names.pop()

    def lookup(self, name):
        for sc in reversed(self.scopes):
            if name in sc:
                return sc[name]
        return None

    def new_slot(self):
        s = self.nslots
        self.nslots += 1
        return s

    def declare(self, name, type_, mutable, category, pos, value=None):
        sym = Symbol(name, category, type_, self.scope_names[-1], pos[0], pos[1],
                     mutable=mutable, slot=self.new_slot(), value=value)
        self.scopes[-1][name] = sym
        self.symbols.append(sym)
        return sym

    # ------------------------------------------------------------------ programa
    def run(self):
        prog = self.program
        # 1) registrar firmas de funciones (permite llamar funciones definidas después)
        for f in prog.functions:
            if f.name in self.funcs:
                self.err(f"La función '{f.name}' ya fue declarada.", f.pos)
                continue
            params = []
            seen = set()
            for p in f.params:
                if p.name in seen:
                    self.err(f"El parámetro '{p.name}' está duplicado en la función '{f.name}'.", p.pos)
                seen.add(p.name)
                params.append((p.name, p.ptype))
            ret = f.ret if f.ret is not None else T.UNIT
            info = FuncInfo(f.name, params, ret, f)
            f.info = info
            self.funcs[f.name] = info
            sym = Symbol(f.name, "Función", ret, "Global", f.pos[0], f.pos[1])
            self.symbols.append(sym)
        # 2) función main
        main = self.funcs.get("main")
        if main is None:
            self.err("No se encontró la función 'main': todo programa debe definir una única función main.", (1, 1))
        else:
            if main.params:
                self.err("La función 'main' no debe recibir parámetros.", main.decl.pos)
            if main.ret != T.UNIT:
                self.err("La función 'main' no debe retornar ningún valor.", main.decl.pos)
        # 3) cuerpos
        for f in prog.functions:
            if getattr(f, "info", None) is not None and self.funcs.get(f.name).decl is f:
                self.check_function(f)
        return self

    def check_function(self, f):
        self.fn = f.info
        self.nslots = 0
        self.loops = []
        self.block_counter = 0
        self.scopes = []
        self.scope_names = []
        self.push_scope(f.name)
        f.param_syms = []
        for p in f.params:
            sym = self.declare(p.name, p.ptype, False, "Parámetro", p.pos)
            f.param_syms.append(sym)
        n_int = sum(1 for _, t in f.info.params if t != T.F64)
        n_flt = sum(1 for _, t in f.info.params if t == T.F64)
        if n_int > 8 or n_flt > 8:
            self.err("Una función admite como máximo 8 parámetros enteros/punteros y 8 de punto flotante.", f.pos)
        for s in f.body.stmts:
            self.stmt(s)
        f.nslots = self.nslots
        self.pop_scope()
        if f.info.ret != T.UNIT and not self.block_terminates(f.body):
            self.err(f"La función '{f.name}' debe retornar un valor de tipo {f.info.ret} en todos los caminos de ejecución.",
                     f.pos)

    # ------------------------------------------------------------------ análisis de retorno
    def block_terminates(self, block):
        return any(self.stmt_terminates(s) for s in block.stmts)

    def stmt_terminates(self, s):
        if isinstance(s, A.Return):
            return True
        if isinstance(s, A.Block):
            return self.block_terminates(s)
        if isinstance(s, A.If):
            if s.orelse is None:
                return False
            return self.block_terminates(s.then) and self.stmt_terminates(s.orelse)
        if isinstance(s, A.Loop):
            return not self.has_break(s.body, s.label, 0)
        if isinstance(s, A.Match):
            has_default = any(isinstance(p, A.Wildcard) for arm in s.arms for p in arm.patterns)
            return has_default and all(self.block_terminates(arm.body) for arm in s.arms)
        return False

    def has_break(self, node, label, depth):
        """¿Hay un break que salga del loop con etiqueta `label` (o sin etiqueta a profundidad 0)?"""
        if isinstance(node, A.Break):
            return (node.label is None and depth == 0) or (node.label is not None and node.label == label)
        if isinstance(node, (A.Loop, A.While)):
            return self.has_break(node.body, label, depth + 1)
        if isinstance(node, A.Block):
            return any(self.has_break(s, label, depth) for s in node.stmts)
        if isinstance(node, A.If):
            return (self.has_break(node.then, label, depth) or
                    (node.orelse is not None and self.has_break(node.orelse, label, depth)))
        if isinstance(node, A.Match):
            return any(self.has_break(arm.body, label, depth) for arm in node.arms)
        return False

    # ------------------------------------------------------------------ sentencias
    def stmt(self, s):
        getattr(self, "s_" + type(s).__name__)(s)

    def block(self, b, kind):
        self.block_counter += 1
        self.push_scope(f"{self.fn.name}:{kind}{self.block_counter}")
        for s in b.stmts:
            self.stmt(s)
        self.pop_scope()

    def s_Block(self, s):
        self.block(s, "bloque")

    def s_VarDecl(self, s):
        it = self.expr(s.init) if s.init is not None else None
        dt = s.ptype
        vtype = dt if dt is not None else it
        if it == T.UNIT:
            self.err("No es posible usar el resultado de una función sin valor de retorno como valor.", s.init.pos)
            it = T.NONE
            vtype = dt if dt is not None else T.NONE
        if dt is not None and it is not None and it != T.NONE and dt != it:
            self.err(f"No es posible asignar un valor de tipo {T.display(it)} a una variable de tipo {T.display(dt)}.",
                     s.init.pos)
        if s.init is None:
            if dt is None:
                self.err(f"No es posible inferir el tipo de '{s.name}': indique un tipo o un valor inicial.", s.pos)
                vtype = T.NONE
            elif T.default_value_kind(dt) is None:
                self.err(f"El tipo {T.display(dt)} no tiene valor por defecto: la variable '{s.name}' debe inicializarse.",
                         s.pos)
        if vtype is None:
            vtype = T.NONE
        value = literal_text(s.init) if s.init is not None else {
            "zero": "0" if vtype != T.F64 else "0.0", "empty": '""', None: "—"}[T.default_value_kind(vtype)]
        if vtype == T.BOOL and s.init is None:
            value = "false"
        s.vtype = vtype
        s.sym = self.declare(s.name, vtype, s.mutable, "Variable", s.pos, value)

    def root_ident(self, n):
        while isinstance(n, (A.Index, A.Slice)):
            n = n.base
        return n if isinstance(n, A.Identifier) else None

    def s_Assign(self, s):
        tgt = s.target
        if not isinstance(tgt, (A.Identifier, A.Index)):
            self.err("El operando izquierdo debe ser una ubicación válida de almacenamiento.", tgt.pos)
            self.expr(s.value)
            s.bin = None
            return
        tt = self.expr(tgt)
        if isinstance(tgt, A.Identifier):
            sym = tgt.sym if hasattr(tgt, "sym") else None
            if sym is not None and not sym.mutable:
                self.err(f"No es posible modificar la variable '{tgt.name}' porque fue declarada como inmutable.", tgt.pos)
        else:
            root = self.root_ident(tgt)
            if STRICT_ARRAY_MUTABILITY and root is not None and getattr(root, "sym", None) is not None \
                    and not root.sym.mutable:
                self.err(f"No es posible modificar elementos de '{root.name}' porque fue declarada como inmutable.",
                         tgt.pos)
        s.bin = None
        if s.op == "=":
            vt = self.expr(s.value)
            if vt == T.UNIT:
                self.err("No es posible asignar el resultado de una función sin valor de retorno.", s.value.pos)
            elif tt != T.NONE and vt != T.NONE and tt != vt:
                self.err(f"No es posible asignar un valor de tipo {T.display(vt)} a una variable de tipo {T.display(tt)}.",
                         s.value.pos)
        else:
            b = A.Binary(s.op[0], tgt, s.value, pos=s.pos)
            rt = self.expr(b)
            s.bin = b
            if tt != T.NONE and rt != T.NONE and tt != rt:
                self.err(f"No es posible asignar un valor de tipo {T.display(rt)} a una variable de tipo {T.display(tt)}.",
                         s.value.pos)

    def s_ExprStmt(self, s):
        self.expr(s.expr)

    # -- println!
    def s_Println(self, s):
        s.pieces = []
        args = s.args
        if not args:
            return
        first = args[0]
        if isinstance(first, A.StrLit):
            self.parse_format(s, first, args[1:])
        else:
            t = self.expr(first)
            if t == T.UNIT:
                self.err("No es posible imprimir el resultado de una función sin valor de retorno.", first.pos)
            if len(args) > 1:
                for a in args[1:]:
                    self.expr(a)
                self.err("println! con una expresión como primer argumento solo admite un argumento.", args[1].pos)
            s.pieces.append(("arg", first, False, None))

    def parse_format(self, s, lit, rest):
        text = lit.value
        pieces = []
        buf = []
        i = 0
        holders = []
        while i < len(text):
            c = text[i]
            if c == "{":
                if text[i + 1:i + 2] == "{":
                    buf.append("{")
                    i += 2
                    continue
                j = text.find("}", i)
                if j < 0:
                    self.err("Marcador de formato sin cerrar: falta '}'.", lit.pos)
                    break
                spec = text[i + 1:j]
                if buf:
                    pieces.append(["lit", "".join(buf)])
                    buf = []
                debug, prec = False, None
                if spec == "":
                    pass
                elif spec == ":?":
                    debug = True
                elif spec.startswith(":.") and spec[2:].isdigit() and int(spec[2:]) <= 9:
                    prec = int(spec[2:])
                else:
                    self.err(f"Especificador de formato no válido: '{{{spec}}}'.", lit.pos)
                pieces.append(["arg", None, debug, prec])
                holders.append(pieces[-1])
                i = j + 1
            elif c == "}":
                if text[i + 1:i + 2] == "}":
                    buf.append("}")
                    i += 2
                    continue
                self.err("Llave '}' sin pareja en la cadena de formato (use '}}').", lit.pos)
                i += 1
            else:
                buf.append(c)
                i += 1
        if buf:
            pieces.append(["lit", "".join(buf)])
        types = [self.expr(a) for a in rest]
        if len(holders) != len(rest):
            self.err(f"El número de argumentos ({len(rest)}) no coincide con los marcadores {{}} ({len(holders)}).",
                     lit.pos)
        for h, a, t in zip(holders, rest, types):
            h[1] = a
            if t == T.UNIT:
                self.err("No es posible imprimir el resultado de una función sin valor de retorno.", a.pos)
            if h[3] is not None and t not in (T.F64, T.NONE):
                self.err(f"La precisión '.{h[3]}' solo puede aplicarse a valores f64.", a.pos)
        s.pieces = [tuple(p) for p in pieces if not (p[0] == "arg" and p[1] is None)]

    # -- control de flujo
    def cond(self, e, what):
        t = self.expr(e)
        if t != T.BOOL and t != T.NONE:
            self.err(f"La condición de {what} debe ser de tipo bool, pero es de tipo {T.display(t)}.", e.pos)

    def s_If(self, s):
        self.cond(s.cond, "if")
        self.block(s.then, "if")
        if s.orelse is not None:
            if isinstance(s.orelse, A.If):
                self.s_If(s.orelse)
            else:
                self.block(s.orelse, "else")

    def s_While(self, s):
        self.cond(s.cond, "while")
        self.loops.append(s.label)
        self.block(s.body, "while")
        self.loops.pop()

    def s_Loop(self, s):
        self.loops.append(s.label)
        self.block(s.body, "loop")
        self.loops.pop()

    def s_Break(self, s):
        self.check_jump(s, "break")

    def s_Continue(self, s):
        self.check_jump(s, "continue")

    def check_jump(self, s, word):
        if not self.loops:
            self.err(f"La sentencia '{word}' solo puede usarse dentro de un ciclo.", s.pos)
        elif s.label is not None and s.label not in self.loops:
            self.err(f"La etiqueta '{s.label}' no corresponde a ningún ciclo que contenga esta sentencia.", s.pos)

    def s_Return(self, s):
        ret = self.fn.ret
        if s.expr is None:
            if ret != T.UNIT:
                self.err(f"La función '{self.fn.name}' debe retornar un valor de tipo {ret}.", s.pos)
            return
        t = self.expr(s.expr)
        if ret == T.UNIT:
            self.err(f"La función '{self.fn.name}' no retorna ningún valor.", s.pos)
        elif t != T.NONE and t != ret:
            self.err(f"Tipos incompatibles. No es posible retornar un valor de tipo {T.display(t)} "
                     f"donde se esperaba un valor de tipo {T.display(ret)}.", s.expr.pos)

    def s_Match(self, s):
        st = self.expr(s.expr)
        s.slot = self.new_slot()
        s.stype = st
        if st not in (T.I32, T.CHAR, T.BOOL, T.STRING, T.NONE):
            self.err(f"No es posible aplicar match sobre un valor de tipo {T.display(st)}.", s.expr.pos)
        has_default = False
        for arm in s.arms:
            for pat in arm.patterns:
                if isinstance(pat, A.Wildcard):
                    has_default = True
                    continue
                pt = {A.IntLit: T.I32, A.CharLit: T.CHAR, A.BoolLit: T.BOOL, A.StrLit: T.STRING,
                      A.FloatLit: T.F64}[type(pat)]
                pat.type = pt
                if pt == T.F64:
                    self.err("No es posible usar literales f64 como patrón de match.", pat.pos)
                elif st != T.NONE and pt != st:
                    self.err(f"Tipos incompatibles. El patrón es de tipo {pt} pero se evalúa un valor de tipo "
                             f"{T.display(st)}.", pat.pos)
            self.block(arm.body, "arm")
        if not has_default:
            self.err("La sentencia match debe incluir una opción comodín '_' que maneje los demás casos.", s.pos)

    # ------------------------------------------------------------------ expresiones
    def expr(self, e):
        t = getattr(self, "e_" + type(e).__name__)(e)
        e.type = t
        return t

    def const_int(self, e):
        if isinstance(e, A.IntLit):
            return e.value
        if isinstance(e, A.Unary) and e.op == "-" and isinstance(e.operand, A.IntLit):
            return -e.operand.value
        return None

    def e_IntLit(self, e):
        if e.value > INT_MAX_LIT:
            self.err(f"El literal {e.value} está fuera del rango de i32.", e.pos)
        return T.I32

    def e_FloatLit(self, e):
        return T.F64

    def e_BoolLit(self, e):
        return T.BOOL

    def e_CharLit(self, e):
        return T.CHAR

    def e_StrLit(self, e):
        return T.STRING

    def e_Wildcard(self, e):
        return T.NONE

    def e_Identifier(self, e):
        sym = self.lookup(e.name)
        if sym is None:
            if e.name in self.funcs:
                self.err(f"'{e.name}' es una función; use '{e.name}(...)' para invocarla.", e.pos)
            else:
                self.err(f"La variable '{e.name}' no ha sido declarada.", e.pos)
            e.sym = None
            return T.NONE
        e.sym = sym
        return sym.type

    def e_Unary(self, e):
        t = self.expr(e.operand)
        if t == T.NONE:
            return T.NONE
        if e.op == "-":
            if t in (T.I32, T.F64):
                return t
        elif t == T.BOOL:
            return T.BOOL
        self.err(f"No es posible aplicar el operador '{e.op}' a un valor de tipo {T.display(t)}.", e.pos)
        return T.NONE

    def e_Binary(self, e):
        lt = self.expr(e.left)
        rt = self.expr(e.right)
        if lt == T.NONE or rt == T.NONE:
            return T.NONE
        op = e.op
        bad = f"No es posible aplicar el operador '{op}' entre los tipos {T.display(lt)} y {T.display(rt)}."
        if op in ("&&", "||"):
            if lt == T.BOOL and rt == T.BOOL:
                return T.BOOL
            self.err(bad + " Los operadores lógicos solo están definidos para bool.", e.pos)
            return T.NONE
        if op in ("==", "!=", "<", ">", "<=", ">="):
            if (lt, rt) in ORDERABLE:
                return T.BOOL
            self.err(bad, e.pos)
            return T.NONE
        res = arith_result(op, lt, rt)
        if res is None or (op in ("-", "/", "%") and res == T.STRING):
            self.err(bad, e.pos)
            return T.NONE
        if op in ("/", "%") and lt == T.I32 and rt == T.I32 and self.const_int(e.right) == 0:
            self.err("División entre cero.", e.right.pos)
        return res

    # -- llamadas
    def e_Call(self, e):
        name = e.name
        e.info = None
        e.builtin = None
        if name == "typeof":
            e.builtin = "typeof"
            if len(e.args) != 1:
                for a in e.args:
                    self.expr(a)
                self.err(f"La función 'typeof' esperaba 1 argumento, pero recibió {len(e.args)}.", e.pos)
                return T.STRING
            t = self.expr(e.args[0])
            e.typeof_name = T.display(t)
            return T.STRING
        if name == "random":
            e.builtin = "random"
            ts = [self.expr(a) for a in e.args]
            if len(e.args) != 2:
                self.err(f"La función 'random' esperaba 2 argumentos, pero recibió {len(e.args)}.", e.pos)
            else:
                for a, t in zip(e.args, ts):
                    if t not in (T.I32, T.NONE):
                        self.err(f"Tipos incompatibles. No es posible utilizar un valor de tipo {T.display(t)} "
                                 f"donde se esperaba un valor de tipo i32.", a.pos)
            return T.I32
        info = self.funcs.get(name)
        ts = [self.expr(a) for a in e.args]
        if info is None:
            if self.lookup(name) is not None:
                self.err(f"'{name}' es una variable, no una función.", e.pos)
            else:
                self.err(f"La función '{name}' no ha sido declarada.", e.pos)
            return T.NONE
        e.info = info
        if len(e.args) != len(info.params):
            self.err(f"La función '{name}' esperaba {len(info.params)} argumentos, pero recibió {len(e.args)}.", e.pos)
            return info.ret
        for a, t, (pn, pt) in zip(e.args, ts, info.params):
            if t != T.NONE and t != pt:
                self.err(f"Tipos incompatibles. No es posible utilizar un valor de tipo {T.display(t)} "
                         f"donde se esperaba un valor de tipo {T.display(pt)} (parámetro '{pn}').", a.pos)
        return info.ret

    def expect_args(self, e, n):
        if len(e.args) != n:
            self.err(f"El método '{e.name}' esperaba {n} argumentos, pero recibió {len(e.args)}.", e.pos)
            return False
        return True

    def e_MethodCall(self, e):
        ot = self.expr(e.obj)
        ats = [self.expr(a) for a in e.args]
        e.otype = ot
        name = e.name
        if ot == T.NONE:
            return T.NONE
        ok = lambda n: self.expect_args(e, n)   # noqa: E731

        def want(i, t):
            if ats[i] != T.NONE and ats[i] != t:
                self.err(f"Tipos incompatibles. No es posible utilizar un valor de tipo {T.display(ats[i])} "
                         f"donde se esperaba un valor de tipo {T.display(t)}.", e.args[i].pos)

        if ot == T.STRING:
            if name in ("len",):
                ok(0)
                return T.I32
            if name == "is_empty":
                ok(0)
                return T.BOOL
            if name in ("to_uppercase", "to_lowercase", "to_string", "clone"):
                ok(0)
                return T.STRING
            if name == "contains":
                if ok(1) and ats[0] not in (T.STRING, T.CHAR, T.NONE):
                    want(0, T.STRING)
                return T.BOOL
            if name == "replace":
                if ok(2):
                    want(0, T.STRING)
                    want(1, T.STRING)
                return T.STRING
            if name == "split":
                if ok(1):
                    want(0, T.STRING)
                return T.VecType(T.STRING)
            if name == "split_whitespace":
                ok(0)
                return T.VecType(T.STRING)
            if name in ("push_str", "push"):
                if ok(1):
                    want(0, T.STRING if name == "push_str" else T.CHAR)
                if not isinstance(e.obj, A.Identifier):
                    self.err(f"El método '{name}' solo puede aplicarse a una variable String.", e.pos)
                elif getattr(e.obj, "sym", None) is not None and not e.obj.sym.mutable:
                    self.err(f"No es posible modificar la variable '{e.obj.name}' porque fue declarada como inmutable.",
                             e.obj.pos)
                return T.UNIT
        elif isinstance(ot, T.ArrayType):
            if name == "len":
                ok(0)
                return T.I32
            if name == "contains":
                if ok(1):
                    if isinstance(ot.elem, T.ArrayType):
                        self.err("El método 'contains' no está definido para arreglos multidimensionales.", e.pos)
                    else:
                        want(0, ot.elem)
                return T.BOOL
            if name == "reverse":
                ok(0)
                root = self.root_ident(e.obj)
                if STRICT_ARRAY_MUTABILITY and root is not None and getattr(root, "sym", None) is not None \
                        and not root.sym.mutable:
                    self.err(f"No es posible modificar '{root.name}' porque fue declarada como inmutable.", e.pos)
                return T.UNIT
        elif isinstance(ot, T.VecType):
            if name == "len":
                ok(0)
                return T.I32
            if name == "is_empty":
                ok(0)
                return T.BOOL
            if name == "collect":
                ok(0)
                return ot
            if name == "contains":
                if ok(1):
                    want(0, ot.elem)
                return T.BOOL
        self.err(f"El método '{name}' no existe para el tipo {T.display(ot)}.", e.pos)
        return T.NONE

    # -- arreglos
    def e_Index(self, e):
        bt = self.expr(e.base)
        it = self.expr(e.index)
        if it not in (T.I32, T.NONE):
            self.err(f"El índice debe ser de tipo i32, pero es de tipo {T.display(it)}.", e.index.pos)
        if bt == T.NONE:
            return T.NONE
        if isinstance(bt, T.ArrayType):
            c = self.const_int(e.index)
            if c is not None and (c < 0 or c >= bt.size):
                self.err("Índice fuera de los límites del arreglo.", e.pos)
            return bt.elem
        if isinstance(bt, T.VecType):
            return bt.elem
        self.err(f"No es posible indexar un valor de tipo {T.display(bt)}.", e.pos)
        return T.NONE

    def e_Slice(self, e):
        bt = self.expr(e.base)
        if bt == T.NONE:
            return T.NONE
        if not isinstance(bt, T.ArrayType):
            self.err(f"Solo es posible crear un slice de un arreglo, no de un valor de tipo {T.display(bt)}.", e.pos)
            return T.NONE
        if e.lo > e.hi or e.hi > bt.size:
            self.err(f"Rango de slice [{e.lo}..{e.hi}] fuera de los límites del arreglo (longitud {bt.size}).", e.pos)
            return T.NONE
        return T.ArrayType(bt.elem, e.hi - e.lo, True)

    def e_ArrayLit(self, e):
        ts = [self.expr(x) for x in e.elems]
        if any(t == T.NONE for t in ts):
            return T.NONE
        first = ts[0]
        if first == T.UNIT:
            self.err("Un arreglo no puede contener valores de tipo ().", e.pos)
            return T.NONE
        for x, t in zip(e.elems, ts):
            if t != first:
                self.err(f"Los elementos de un arreglo deben ser del mismo tipo: se esperaba {T.display(first)} "
                         f"pero se encontró {T.display(t)}.", x.pos)
                return T.NONE
        return T.ArrayType(first, len(e.elems))

    def e_ArrayRepeat(self, e):
        t = self.expr(e.value)
        if t == T.NONE:
            return T.NONE
        if e.count < 1:
            self.err("El tamaño de un arreglo debe ser al menos 1.", e.pos)
            return T.NONE
        return T.ArrayType(t, e.count)

    def e_StringFrom(self, e):
        t = self.expr(e.arg)
        if t not in (T.STRING, T.NONE):
            self.err(f"String::from espera un valor de tipo String, pero recibió {T.display(t)}.", e.pos)
        return T.STRING

    def e_StringNew(self, e):
        return T.STRING
