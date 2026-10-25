"""Generación de código ensamblador ARM64 (AArch64, sintaxis GNU as)"""

import struct

from . import ast_nodes as A
from . import runtime as RT
from . import typesys as T
from .semantic import arithmetic_result, unparse

CC_INT = {"==": "eq", "!=": "ne", "<": "lt", "<=": "le", ">": "gt", ">=": "ge"}
CC_FLT = {"==": "eq", "!=": "ne", "<": "mi", "<=": "ls", ">": "gt", ">=": "ge"}


def asm_string(s):
    """Literal .asciz con escapes octales para bytes no imprimibles."""
    out = []
    for b in s.encode("utf-8"):
        if b == 34:
            out.append('\\"')
        elif b == 92:
            out.append("\\\\")
        elif 32 <= b < 127:
            out.append(chr(b))
        else:
            out.append("\\%03o" % b)
    return '"' + "".join(out) + '"'


class LoopCtx:
    def __init__(self, label, brk, cont):
        self.label, self.brk, self.cont = label, brk, cont


class CodeGenerator:
    def __init__(self, program, table):
        self.program = program
        self.table = table
        self.lines = []
        self.nlabel = 0
        self.strings = {}
        self.doubles = {}
        self.used = {"_exit", "_flush"}
        self.helpers = {}  # (tipo, debug) -> etiqueta del impresor de arreglos
        self.helper_code = []
        self.globals = []
        self.loops = []
        self.nslots = 0
        self.fn = None
        self.ret_label = None
        self.gcount = 0

    # ==================================================================
    # utilidades de emisión
    # ==================================================================
    def emit(self, s):
        self.lines.append("    " + s)

    def raw(self, s):
        self.lines.append(s)

    def comment(self, s):
        self.lines.append("    // " + s)

    def label(self, l):
        self.lines.append(f"{l}:")

    def new_label(self, p="L"):
        self.nlabel += 1
        return f".L{p}{self.nlabel}"

    def rt(self, name):
        self.used.add(name)
        self.emit(f"bl   {name}")

    def load_int(self, reg, v):
        v = int(v)
        if v < 0:
            v &= 0xFFFFFFFFFFFFFFFF
        if v == 0:
            self.emit(f"mov  {reg}, #0")
            return
        if v <= 0xFFFF:
            self.emit(f"mov  {reg}, #{v}")
            return
        neg = (~v) & 0xFFFFFFFFFFFFFFFF
        if neg <= 0xFFFF:
            self.emit(f"movn {reg}, #{neg}")
            return
        first = True
        for sh in (0, 16, 32, 48):
            part = (v >> sh) & 0xFFFF
            if part == 0 and not (first and v == 0):
                continue
            if first:
                self.emit(f"movz {reg}, #{part}" + (f", lsl #{sh}" if sh else ""))
                first = False
            else:
                self.emit(f"movk {reg}, #{part}" + (f", lsl #{sh}" if sh else ""))

    def str_label(self, s):
        if s not in self.strings:
            self.strings[s] = f".LS{len(self.strings)}"
        return self.strings[s]

    def load_str(self, s, reg="x0"):
        lab = self.str_label(s)
        self.emit(f"adrp {reg}, {lab}")
        self.emit(f"add  {reg}, {reg}, :lo12:{lab}")

    def load_double(self, v, reg="d0"):
        bits = struct.unpack("<Q", struct.pack("<d", float(v)))[0]
        if bits not in self.doubles:
            self.doubles[bits] = f".LD{len(self.doubles)}"
        lab = self.doubles[bits]
        self.emit(f"adrp x16, {lab}")
        self.emit(f"ldr  {reg}, [x16, :lo12:{lab}]")

    # memoria de pila ------------------------------------------------------
    def alloc_slot(self):
        i = self.nslots
        self.nslots += 1
        return i

    def mem(self, op, reg, off):
        """Acceso a [x29 + off] cuidando el rango del desplazamiento."""
        if off <= 32760:
            self.emit(f"{op:<4} {reg}, [x29, #{off}]")
        else:
            self.load_int("x16", off)
            self.emit("add  x16, x29, x16")
            self.emit(f"{op:<4} {reg}, [x16]")

    def slot_off(self, i):
        return 16 + 8 * i

    def load_slot(self, i, t):
        self.mem("ldr", "d0" if t == T.F64 else "x0", self.slot_off(i))

    def store_slot(self, i, t):
        self.mem("str", "d0" if t == T.F64 else "x0", self.slot_off(i))

    def push(self, t):
        self.emit("str  d0, [sp, #-16]!" if t == T.F64 else "str  x0, [sp, #-16]!")

    def pop(self, t, n="1"):
        self.emit(f"ldr  d{n}, [sp], #16" if t == T.F64 else f"ldr  x{n}, [sp], #16")

    def gen(self, node):
        t = node.type
        if t is not None and t.is_none and not isinstance(node, A.Assign):
            self.emit("mov  x0, #0              // expresión con error (None)")
            return
        node.accept(self)

    def gen_cond(self, node):
        """Condición booleana; si su tipo es inválido (error semántico) se toma como falsa."""
        if node.type == T.BOOL:
            self.gen(node)
        else:
            self.emit("mov  x0, #0              // condición inválida: se asume false")

    def gen_as(self, node, target):
        """Genera `node` y lo convierte a `target` (promoción i32 -> f64)."""
        self.gen(node)
        if target == T.F64 and node.type == T.I32:
            self.emit("scvtf d0, x0")

    # ==================================================================
    # programa
    # ==================================================================
    def generate(self):
        # globales primero: asigna etiquetas antes de generar las funciones
        ginit = []
        gvars = [i for i in self.program.items if isinstance(i, A.VarDecl)]
        if gvars:
            self.lines = []
            self.gen_init_globals(gvars)
            ginit = self.lines
        body = []
        for item in self.program.items:
            if isinstance(item, A.Function):
                if item.sym is not None and item.sym.node is item:
                    self.lines = []
                    self.visit_Function(item)
                    body.extend(self.lines)

        out = []
        out.append("// ================================================================")
        out.append("// Código ARM64 (AArch64, GNU as) generado por el compilador OxigenNative")
        out.append("// ================================================================")
        out.append(".text")
        out.append(".global _start")
        out.append("")
        out.append("// ---- Punto de entrada: inicializa globales, ejecuta main y sale ----")
        out.append("_start:")
        out.append("    mov  x29, #0")
        if gvars:
            out.append("    bl   _init_globals")
        out.append("    bl   main")
        out.append("    mov  x0, #0")
        out.append("    b    _exit")
        out.append("")
        out.extend(ginit)
        if ginit:
            out.append("")
        out.append("// ================= Funciones del programa =================")
        out.extend(body)
        # helpers de impresión de arreglos
        if self.helper_code:
            out.append("// ============ Impresores de arreglos (generados) ============")
            out.extend(self.helper_code)
        # runtime
        order = RT.resolve(self.used)
        out.append("// ================= Runtime (ver docs) =================")
        for name in order:
            out.append(RT.ROUTINES[name])
        # datos
        out.append(".section .rodata")
        out.append(".balign 8")
        for s, lab in self.strings.items():
            out.append(f"{lab}: .asciz {asm_string(s)}")
        for bits, lab in self.doubles.items():
            out.append(f".balign 8\n{lab}: .quad 0x{bits:016x}")
        for name in order:
            if name in RT.DATA:
                out.append(RT.DATA[name])
        out.append(".data")
        out.append(".balign 8")
        out.append("_outpos: .quad 0")
        out.append("_heap_cur: .quad 0")
        out.append("_rng: .quad 0")
        for lab in self.globals:
            out.append(f"{lab}: .quad 0")
        out.append(".bss")
        out.append(".balign 16")
        out.append("_outbuf: .skip 65536")
        if "_alloc" in order:
            out.append(".balign 16")
            out.append("_heap: .skip 134217728")
            out.append("_heap_end:")
        return "\n".join(out) + "\n"

    # ------------------------------------------------------------------
    def begin_function(self, name, label, is_main=False):
        self.nslots = 0
        self.loops = []
        self.fn = name
        self.ret_label = f".Lret_{name}"

    def finish_function(self, label, header_comment, param_stores, body_lines, is_main=False):
        frame = 16 + 8 * self.nslots
        frame = (frame + 15) & ~15
        out = [header_comment]
        if is_main:
            out.append(".global main")
        out.append(f"{label}:")
        out.append(f"    // prólogo: reserva stack frame de {frame} bytes (x29=frame pointer, x30=link register)")
        if frame <= 504:
            out.append(f"    stp  x29, x30, [sp, #-{frame}]!")
        else:
            if frame <= 4095:
                out.append(f"    sub  sp, sp, #{frame}")
            else:
                self.lines = []
                self.load_int("x16", frame)
                out.extend(self.lines)
                out.append("    sub  sp, sp, x16")
            out.append("    stp  x29, x30, [sp]")
        out.append("    mov  x29, sp")
        self.lines = []
        for st in param_stores:
            st()
        out.extend(self.lines)
        out.extend(body_lines)
        out.append(f"{self.ret_label}:")
        out.append("    // epílogo: restaura registros y retorna")
        if frame <= 504:
            out.append(f"    ldp  x29, x30, [sp], #{frame}")
        else:
            out.append("    ldp  x29, x30, [sp]")
            if frame <= 4095:
                out.append(f"    add  sp, sp, #{frame}")
            else:
                self.lines = []
                self.load_int("x16", frame)
                out.extend(self.lines)
                out.append("    add  sp, sp, x16")
        out.append("    ret")
        out.append("")
        return out

    def visit_Function(self, f):
        fs = f.sym
        self.begin_function(f.name, fs.label, f.name == "main")
        # parámetros -> slots
        ni = nf = 0
        stores = []
        for p in f.params:
            slot = self.alloc_slot()
            p.sym.slot = slot
            if p.ptype == T.F64:
                stores.append(lambda s=slot, r=nf: self.mem("str", f"d{r}", self.slot_off(s)))
                nf += 1
            else:
                stores.append(lambda s=slot, r=ni: self.mem("str", f"x{r}", self.slot_off(s)))
                ni += 1
        self.lines = []
        for s in f.body.stmts:
            s.accept(self)
        body = self.lines
        sig = ", ".join(f"{p.name}: {p.ptype}" for p in f.params)
        ret = f" -> {fs.ret}" if fs.ret != T.UNIT else ""
        hdr = f"// ---- fn {f.name}({sig}){ret}  [parámetros: x0-x7 / d0-d7, retorno: x0 / d0] ----"
        self.lines = self.finish_function(fs.label, hdr, stores, body, f.name == "main")

    def gen_init_globals(self, gvars):
        self.begin_function("_init_globals", "_init_globals")
        self.ret_label = ".Lret__init_globals"
        self.lines = []
        for g in gvars:
            self.visit_VarDecl(g)
        body = self.lines
        self.lines = self.finish_function(
            "_init_globals", "// ---- inicialización de variables globales ----", [], body)

    # ==================================================================
    # sentencias
    # ==================================================================
    def zero_value(self, t):
        """Valor por defecto en x0 / d0 para el tipo t."""
        if t == T.STRING:
            self.load_str("")
        elif t.kind == "array":
            self.load_int("x0", t.byte_size())
            self.rt("_alloc")
        elif t.kind == "struct":
            self.load_int("x0", max(8, t.byte_size()))
            self.rt("_alloc")
        elif t.kind == "vec":
            self.emit("mov  x0, #16")
            self.rt("_alloc")
            self.emit("add  x0, x0, #8")
        elif t.kind == "slice":
            self.load_int("x0", max(8, t.n * t.elem.byte_size()))
            self.rt("_alloc")
        elif t == T.F64:
            self.emit("fmov d0, xzr")
        else:
            self.emit("mov  x0, #0")

    def store_var(self, sym):
        t = sym.type
        reg = "d0" if t == T.F64 else "x0"
        if sym.is_global:
            self.emit(f"adrp x16, {sym.label}")
            self.emit(f"str  {reg}, [x16, :lo12:{sym.label}]")
        else:
            self.mem("str", reg, self.slot_off(sym.slot))

    def load_var(self, sym):
        t = sym.type
        reg = "d0" if t == T.F64 else "x0"
        if sym.is_global:
            self.emit(f"adrp x16, {sym.label}")
            self.emit(f"ldr  {reg}, [x16, :lo12:{sym.label}]")
        else:
            self.mem("ldr", reg, self.slot_off(sym.slot))

    def visit_VarDecl(self, d):
        sym = d.sym
        decl = ("let mut " if d.mutable else "let ") + d.name + (f": {sym.type}" if d.type_ann else "")
        if d.init is not None:
            self.comment(f"{decl} = {unparse(d.init)};")
        else:
            self.comment(f"{decl};   (valor por defecto)")
        if sym.is_global:
            self.gcount += 1
            sym.label = f"g_{sym.name}_{self.gcount}"
            self.globals.append(sym.label)
        else:
            sym.slot = self.alloc_slot()
        t = sym.type
        if d.init is not None and not (d.init.type is not None and d.init.type.is_none):
            self.gen_as(d.init, t)
        else:
            self.zero_value(t)
        self.store_var(sym)

    def visit_ExprStmt(self, s):
        self.comment(unparse(s.expr) + ";")
        self.gen(s.expr)

    def visit_Block(self, b):
        for s in b.stmts:
            s.accept(self)

    def visit_Assign(self, s):
        if not s.ok:
            return
        self.comment(f"{unparse(s.target)} {s.op} {unparse(s.value)};")
        t = s.target.type
        if s.op == "=":
            self.gen_as(s.value, t)
        else:
            b = A.Binary(s.op[0], s.target, s.value)
            b.line, b.col = s.line, s.col
            b.type = arithmetic_result(s.op[0], s.target.type, s.value.type)
            self.visit_Binary(b)
            if t == T.F64 and b.type == T.I32:
                self.emit("scvtf d0, x0")
        self.store_target(s.target, t)

    def store_target(self, target, t):
        """Guarda el valor de x0/d0 en la variable o elemento `target`."""
        if isinstance(target, A.Identifier):
            self.store_var(target.sym)
            return
        self.push(t)
        self.gen_addr(target)
        self.pop(t)
        self.emit("str  d1, [x0]" if t == T.F64 else "str  x1, [x0]")

    def visit_If(self, s):
        self.comment(f"if {unparse(s.cond)} {{ ... }}")
        end = self.new_label("endif")
        els = self.new_label("else") if s.else_ is not None else end
        self.gen_cond(s.cond)
        self.emit(f"cbz  x0, {els}")
        s.then.accept(self)
        if s.else_ is not None:
            self.emit(f"b    {end}")
            self.label(els)
            s.else_.accept(self)
        self.label(end)

    def visit_While(self, s):
        self.comment(f"while {unparse(s.cond)} {{ ... }}")
        top, end = self.new_label("while"), self.new_label("endwhile")
        self.loops.append(LoopCtx(s.label, end, top))
        self.label(top)
        self.gen_cond(s.cond)
        self.emit(f"cbz  x0, {end}")
        s.body.accept(self)
        self.emit(f"b    {top}")
        self.label(end)
        self.loops.pop()

    def visit_Loop(self, s):
        self.comment("loop { ... }")
        top, end = self.new_label("loop"), self.new_label("endloop")
        self.loops.append(LoopCtx(s.label, end, top))
        self.label(top)
        s.body.accept(self)
        self.emit(f"b    {top}")
        self.label(end)
        self.loops.pop()

    def visit_For(self, s):
        it = s.iterable
        top, cont, end = self.new_label("for"), self.new_label("forstep"), self.new_label("endfor")
        s.sym.slot = self.alloc_slot()
        var = s.sym.slot
        if isinstance(it, A.Range):
            self.comment(f"for {s.var} in {unparse(it)} {{ ... }}")
            hi = self.alloc_slot()
            self.gen_as(it.lo, T.I32)
            self.store_slot(var, T.I32)
            self.gen_as(it.hi, T.I32)
            self.store_slot(hi, T.I32)
            self.loops.append(LoopCtx(s.label, end, cont))
            self.label(top)
            self.load_slot(var, T.I32)
            self.emit("mov  x1, x0")
            self.load_slot(hi, T.I32)
            self.emit("cmp  x1, x0")
            self.emit(f"b.gt {end}" if it.inclusive else f"b.ge {end}")
            s.body.accept(self)
            self.label(cont)
            self.load_slot(var, T.I32)
            self.emit("add  x0, x0, #1")
            self.store_slot(var, T.I32)
            self.emit(f"b    {top}")
            self.label(end)
            self.loops.pop()
            return
        # recorrido de arreglo / slice / vec
        self.comment(f"for {s.var} in {unparse(it)} {{ ... }}")
        t = it.type
        p, n, i = self.alloc_slot(), self.alloc_slot(), self.alloc_slot()
        self.gen(it)
        self.mem("str", "x0", self.slot_off(p))
        if t.kind == "vec":
            self.emit("ldr  x0, [x0, #-8]")
        else:
            self.load_int("x0", t.n)
        self.mem("str", "x0", self.slot_off(n))
        self.emit("mov  x0, #0")
        self.mem("str", "x0", self.slot_off(i))
        self.loops.append(LoopCtx(s.label, end, cont))
        self.label(top)
        self.mem("ldr", "x0", self.slot_off(i))
        self.mem("ldr", "x1", self.slot_off(n))
        self.emit("cmp  x0, x1")
        self.emit(f"b.hs {end}")
        self.mem("ldr", "x1", self.slot_off(p))
        self.elem_at(t.elem, "x1", "x0")
        self.store_slot(var, t.elem)
        s.body.accept(self)
        self.label(cont)
        self.mem("ldr", "x0", self.slot_off(i))
        self.emit("add  x0, x0, #1")
        self.mem("str", "x0", self.slot_off(i))
        self.emit(f"b    {top}")
        self.label(end)
        self.loops.pop()

    def elem_at(self, elem, base, idx):
        """Carga el elemento `idx` del bloque `base` en x0/d0 (o su dirección)."""
        size = elem.byte_size()
        self.load_int("x2", size)
        self.emit(f"madd x1, {idx}, x2, {base}")
        if elem.is_aggregate:
            self.emit("mov  x0, x1")
        elif elem == T.F64:
            self.emit("ldr  d0, [x1]")
        else:
            self.emit("ldr  x0, [x1]")

    def visit_Match(self, s):
        self.comment(f"match {unparse(s.subject)} {{ ... }}")
        st = s.subject.type
        slot = self.alloc_slot()
        self.gen(s.subject)
        self.store_slot(slot, st)
        end = self.new_label("endmatch")
        bodies = [self.new_label("arm") for _ in s.arms]
        for arm, body in zip(s.arms, bodies):
            for pat in arm.patterns:
                if isinstance(pat, A.Wildcard):
                    self.emit(f"b    {body}")
                    continue
                nxt = self.new_label("next")
                if isinstance(pat, A.Range):
                    self.gen(pat.lo)
                    self.emit("mov  x1, x0")
                    self.load_slot(slot, T.I32)
                    self.emit("cmp  x0, x1")
                    self.emit(f"b.lt {nxt}")
                    self.gen(pat.hi)
                    self.emit("mov  x1, x0")
                    self.load_slot(slot, T.I32)
                    self.emit("cmp  x0, x1")
                    self.emit(f"b.gt {nxt}" if pat.inclusive else f"b.ge {nxt}")
                    self.emit(f"b    {body}")
                elif st == T.STRING:
                    self.gen(pat)
                    self.emit("mov  x1, x0")
                    self.load_slot(slot, T.STRING)
                    self.rt("_str_cmp")
                    self.emit(f"cbz  x0, {body}")
                else:
                    self.gen(pat)
                    self.emit("mov  x1, x0")
                    self.load_slot(slot, T.I32)
                    self.emit("cmp  x0, x1")
                    self.emit(f"b.eq {body}")
                self.label(nxt)
        self.emit(f"b    {end}")
        for arm, body in zip(s.arms, bodies):
            self.label(body)
            arm.body.accept(self)
            self.emit(f"b    {end}")
        self.label(end)

    def _find_loop(self, label):
        for ctx in reversed(self.loops):
            if label is None or ctx.label == label:
                return ctx
        return None

    def visit_Break(self, s):
        ctx = self._find_loop(s.label)
        self.comment("break" + (f" {s.label}" if s.label else ""))
        if ctx:
            self.emit(f"b    {ctx.brk}")

    def visit_Continue(self, s):
        ctx = self._find_loop(s.label)
        self.comment("continue" + (f" {s.label}" if s.label else ""))
        if ctx:
            self.emit(f"b    {ctx.cont}")

    def visit_Return(self, s):
        self.comment("return" + (f" {unparse(s.value)}" if s.value else ""))
        if s.value is not None:
            fs = self.table.funcs.get(self.fn)
            self.gen_as(s.value, fs.ret if fs else s.value.type)
        self.emit(f"b    {self.ret_label}")

    # ==================================================================
    # expresiones
    # ==================================================================
    def visit_Literal(self, e):
        k = e.kind
        if k == "i32":
            self.load_int("x0", e.value)
        elif k == "bool":
            self.emit(f"mov  x0, #{1 if e.value else 0}")
        elif k == "char":
            self.load_int("x0", ord(e.value))
        elif k == "f64":
            self.load_double(e.value)
        else:
            self.load_str(e.value)

    def visit_Identifier(self, e):
        self.load_var(e.sym)

    def visit_Unary(self, e):
        self.gen(e.operand)
        if e.op == "-":
            if e.type == T.F64:
                self.emit("fneg d0, d0")
            else:
                self.emit("neg  x0, x0")
                self.emit("sxtw x0, w0")
        else:
            self.emit("eor  x0, x0, #1")

    def visit_Cast(self, e):
        self.gen(e.expr)
        s, d = e.expr.type, e.target
        if s == d:
            return
        if s == T.I32 and d == T.F64:
            self.emit("scvtf d0, x0")
        elif s == T.F64 and d == T.I32:
            self.emit("fcvtzs x0, d0")
            self.emit("sxtw x0, w0")

    def visit_Binary(self, e):
        op = e.op
        if op in ("&&", "||"):
            end = self.new_label("sc")
            self.gen(e.left)
            self.emit(f"cbz  x0, {end}" if op == "&&" else f"cbnz x0, {end}")
            self.gen(e.right)
            self.label(end)
            return
        lt, rt = e.left.type, e.right.type
        # cadenas
        if lt == T.STRING or rt == T.STRING:
            self.gen(e.left)
            self.push(lt)
            self.gen(e.right)
            self.emit("mov  x1, x0")
            self.emit("ldr  x0, [sp], #16")
            if op == "+":
                self.rt("_str_concat")
            elif op == "*":
                if lt == T.I32:  # n * "s"
                    self.emit("mov  x2, x0")
                    self.emit("mov  x0, x1")
                    self.emit("mov  x1, x2")
                self.rt("_str_repeat")
            else:
                self.rt("_str_cmp")
                self.emit("cmp  x0, #0")
                self.emit(f"cset x0, {CC_INT[op]}")
            return
        opt = T.F64 if (lt == T.F64 or rt == T.F64) else T.I32
        self.gen_as(e.left, opt)
        self.push(opt)
        self.gen_as(e.right, opt)
        self.pop(opt, "1")  # izquierda en x1/d1, derecha en x0/d0
        if opt == T.F64:
            if op in CC_FLT:
                self.emit("fcmp d1, d0")
                self.emit(f"cset x0, {CC_FLT[op]}")
            elif op == "+":
                self.emit("fadd d0, d1, d0")
            elif op == "-":
                self.emit("fsub d0, d1, d0")
            elif op == "*":
                self.emit("fmul d0, d1, d0")
            elif op == "/":
                self.emit("fdiv d0, d1, d0")
            elif op == "%":
                self.emit("fdiv d2, d1, d0")
                self.emit("frintz d2, d2")
                self.emit("fmsub d0, d2, d0, d1")
            return
        if op in CC_INT:
            self.emit("cmp  x1, x0")
            self.emit(f"cset x0, {CC_INT[op]}")
        elif op == "+":
            self.emit("add  x0, x1, x0")
            self.emit("sxtw x0, w0")
        elif op == "-":
            self.emit("sub  x0, x1, x0")
            self.emit("sxtw x0, w0")
        elif op == "*":
            self.emit("mul  x0, x1, x0")
            self.emit("sxtw x0, w0")
        elif op in ("/", "%"):
            self.used.add("_panic_div0")
            self.emit("cbz  x0, _panic_div0")
            if op == "/":
                self.emit("sdiv x0, x1, x0")
            else:
                self.emit("sdiv x2, x1, x0")
                self.emit("msub x0, x2, x0, x1")
            self.emit("sxtw x0, w0")

    # ---- arreglos ---------------------------------------------------------------
    def gen_addr(self, e):
        """Deja en x0 la dirección del elemento `e` (un Index o un FieldAccess)."""
        if isinstance(e, A.FieldAccess):
            self.gen(e.base)
            if e.offset:
                self.load_int("x1", e.offset)
                self.emit("add  x0, x0, x1")
            return
        bt = e.base.type
        self.gen(e.base)
        self.emit("str  x0, [sp, #-16]!")
        self.gen_as(e.index, T.I32)
        self.emit("ldr  x1, [sp], #16")
        self.used.add("_panic_oob")
        if bt.kind == "vec":
            self.emit("ldr  x2, [x1, #-8]")
            self.emit("cmp  x0, x2")
        else:
            if bt.n <= 4095:
                self.emit(f"cmp  x0, #{bt.n}")
            else:
                self.load_int("x2", bt.n)
                self.emit("cmp  x0, x2")
        self.emit("b.hs _panic_oob")
        self.load_int("x2", bt.elem.byte_size())
        self.emit("madd x0, x0, x2, x1")

    def visit_FieldAccess(self, e):
        self.gen_addr(e)
        if e.type.is_aggregate:
            return
        self.emit("ldr  d0, [x0]" if e.type == T.F64 else "ldr  x0, [x0]")

    def visit_StructLit(self, e):
        t = e.type
        self.load_int("x0", max(8, t.byte_size()))
        self.rt("_alloc")
        self.emit("str  x0, [sp, #-16]!")
        for fname, val, _, _ in e.inits:
            r = t.field_offset(fname)
            if r is None:
                continue
            off, ft = r
            if val.type is not None and val.type.is_none or ft.is_none:
                continue
            if ft.is_aggregate:
                self.gen(val)
                self.emit("mov  x1, x0")
                self.emit("ldr  x0, [sp]")
                if off:
                    self.load_int("x3", off)
                    self.emit("add  x0, x0, x3")
                self.load_int("x2", ft.byte_size())
                self.rt("_memcpy")
            else:
                self.gen_as(val, ft)
                self.store_slot_at(ft, off)
        self.emit("ldr  x0, [sp], #16")

    def visit_Index(self, e):
        self.gen_addr(e)
        et = e.type
        if et.is_aggregate:
            return
        self.emit("ldr  d0, [x0]" if et == T.F64 else "ldr  x0, [x0]")

    def visit_SliceExpr(self, e):
        self.gen(e.base)
        bt = e.base.type
        if bt.kind == "vec":
            self.emit("ldr  x1, [x0, #-8]")
            self.load_int("x2", e.hi)
            self.emit("cmp  x2, x1")
            self.used.add("_panic_oob")
            self.emit("b.hi _panic_oob")
        off = e.lo * bt.elem.byte_size()
        if off:
            if off <= 4095:
                self.emit(f"add  x0, x0, #{off}")
            else:
                self.load_int("x1", off)
                self.emit("add  x0, x0, x1")

    def visit_ArrayLit(self, e):
        t = e.type
        self.load_int("x0", max(8, t.byte_size()))
        self.rt("_alloc")
        self.emit("str  x0, [sp, #-16]!")
        self.fill_array(e, t, 0)
        self.emit("ldr  x0, [sp], #16")

    def store_slot_at(self, t, byteoff):
        """Guarda x0/d0 en [bloque + byteoff]; el bloque está en [sp]."""
        reg = "d0" if t == T.F64 else "x0"
        self.emit("ldr  x1, [sp]")
        if byteoff <= 32760:
            self.emit(f"str  {reg}, [x1, #{byteoff}]")
        else:
            self.load_int("x2", byteoff)
            self.emit(f"str  {reg}, [x1, x2]")

    def fill_array(self, lit, atype, base_slot):
        et = atype.elem
        es = et.slots()
        for i, el in enumerate(lit.elems):
            off = (base_slot + i * es)
            if isinstance(el, A.ArrayLit) and et.kind == "array":
                self.fill_array(el, et, off)
            elif et.is_aggregate:
                self.gen(el)
                self.emit("mov  x1, x0")
                self.emit("ldr  x0, [sp]")
                if off * 8:
                    self.load_int("x3", off * 8)
                    self.emit("add  x0, x0, x3")
                self.load_int("x2", et.byte_size())
                self.rt("_memcpy")
            else:
                self.gen_as(el, et)
                self.store_slot_at(et, off * 8)

    def visit_ArrayRepeat(self, e):
        t = e.type
        et = t.elem
        self.load_int("x0", max(8, t.byte_size()))
        self.rt("_alloc")
        self.emit("str  x0, [sp, #-16]!")
        self.gen_as(e.elem, et)
        if et.is_aggregate:
            self.emit("mov  x4, x0")
            for i in range(e.count):
                self.emit("ldr  x0, [sp]")
                self.load_int("x3", i * et.byte_size())
                self.emit("add  x0, x0, x3")
                self.emit("mov  x1, x4")
                self.load_int("x2", et.byte_size())
                self.rt("_memcpy")
                self.emit("mov  x4, x4") if False else None
        else:
            self.emit("fmov x2, d0" if et == T.F64 else "mov  x2, x0")
            self.emit("ldr  x0, [sp]")
            self.load_int("x1", e.count)
            self.rt("_arr_fill")
        self.emit("ldr  x0, [sp], #16")

    # ---- llamadas ---------------------------------------------------------------
    def visit_Call(self, e):
        f = e.func
        if f == "typeof":
            self.load_str(e.static_str)
            return
        if f == "random":
            self.gen_as(e.args[0], T.I32)
            self.emit("str  x0, [sp, #-16]!")
            self.gen_as(e.args[1], T.I32)
            self.emit("mov  x1, x0")
            self.emit("ldr  x0, [sp], #16")
            self.rt("_random")
            return
        if f is None:  # llamada inválida: valor neutro
            self.zero_value(e.type if e.type is not None else T.I32)
            return
        n = len(e.args)
        for a, (_, pt) in zip(e.args, f.params):
            self.gen_as(a, pt)
            self.push(pt)
        ni = nf = 0
        for k, (a, (_, pt)) in enumerate(zip(e.args, f.params)):
            off = 16 * (n - 1 - k)
            if pt == T.F64:
                self.emit(f"ldr  d{nf}, [sp, #{off}]")
                nf += 1
            else:
                self.emit(f"ldr  x{ni}, [sp, #{off}]")
                ni += 1
        if n:
            self.emit(f"add  sp, sp, #{16 * n}")
        self.emit(f"bl   {f.label}")

    def visit_StaticCall(self, e):
        if e.name == "from":
            self.gen(e.args[0])
        else:
            self.load_str("")

    def visit_MethodCall(self, e):
        name, ot = e.name, e.obj.type
        if name == "len":
            if ot == T.STRING:
                self.gen(e.obj)
                self.rt("_strlen")
            elif ot.kind == "vec":
                self.gen(e.obj)
                self.emit("ldr  x0, [x0, #-8]")
            else:
                self.load_int("x0", ot.n)
        elif name == "contains":
            if ot == T.STRING:
                self.gen(e.obj)
                self.emit("str  x0, [sp, #-16]!")
                self.gen(e.args[0])
                self.emit("mov  x1, x0")
                self.emit("ldr  x0, [sp], #16")
                self.rt("_str_contains")
            else:
                self.gen_seq_contains(e)
        elif name == "replace":
            self.gen(e.obj)
            self.emit("str  x0, [sp, #-16]!")
            self.gen(e.args[0])
            self.emit("str  x0, [sp, #-16]!")
            self.gen(e.args[1])
            self.emit("mov  x2, x0")
            self.emit("ldr  x1, [sp], #16")
            self.emit("ldr  x0, [sp], #16")
            self.rt("_str_replace")
        elif name == "split":
            self.gen(e.obj)
            self.emit("str  x0, [sp, #-16]!")
            self.gen(e.args[0])
            self.emit("mov  x1, x0")
            self.emit("ldr  x0, [sp], #16")
            self.rt("_str_split")
        elif name == "split_whitespace":
            self.gen(e.obj)
            self.rt("_str_split_ws")
        elif name == "collect":
            self.gen(e.obj)
        elif name == "to_uppercase":
            self.gen(e.obj)
            self.rt("_str_upper")
        elif name == "to_lowercase":
            self.gen(e.obj)
            self.rt("_str_lower")
        elif name == "push_str":
            self.gen(e.obj)
            self.emit("str  x0, [sp, #-16]!")
            self.gen(e.args[0])
            self.emit("mov  x1, x0")
            self.emit("ldr  x0, [sp], #16")
            self.rt("_str_concat")
            self.store_target(e.obj, T.STRING)
        elif name == "reverse":
            self.gen(e.obj)
            if ot.kind == "vec":
                self.emit("ldr  x1, [x0, #-8]")
            else:
                self.load_int("x1", ot.n)
            self.load_int("x2", ot.elem.byte_size())
            self.rt("_arr_reverse")

    def gen_eq(self, t):
        """Compara izquierda (x1/d1) con derecha (x0/d0) -> x0 = 0/1."""
        if t == T.STRING:
            self.emit("mov  x2, x0")
            self.emit("mov  x0, x1")
            self.emit("mov  x1, x2")
            self.rt("_str_cmp")
            self.emit("cmp  x0, #0")
            self.emit("cset x0, eq")
        elif t == T.F64:
            self.emit("fcmp d1, d0")
            self.emit("cset x0, eq")
        else:
            self.emit("cmp  x1, x0")
            self.emit("cset x0, eq")

    def gen_seq_contains(self, e):
        t = e.obj.type
        et = t.elem
        p, n, v, i = (self.alloc_slot() for _ in range(4))
        self.gen(e.obj)
        self.mem("str", "x0", self.slot_off(p))
        if t.kind == "vec":
            self.emit("ldr  x0, [x0, #-8]")
        else:
            self.load_int("x0", t.n)
        self.mem("str", "x0", self.slot_off(n))
        self.gen_as(e.args[0], et)
        self.store_slot(v, et)
        self.emit("mov  x0, #0")
        self.mem("str", "x0", self.slot_off(i))
        top, found, end = self.new_label("ct"), self.new_label("ctyes"), self.new_label("ctend")
        self.label(top)
        self.mem("ldr", "x0", self.slot_off(i))
        self.mem("ldr", "x1", self.slot_off(n))
        self.emit("cmp  x0, x1")
        self.emit(f"b.hs {end}")
        self.mem("ldr", "x1", self.slot_off(p))
        self.emit("lsl  x0, x0, #3")
        self.emit("ldr  x2, [x1, x0]")
        if et == T.F64:
            self.emit("fmov d1, x2")
        else:
            self.emit("mov  x1, x2")
        self.load_slot(v, et)
        self.gen_eq(et)
        self.emit(f"cbnz x0, {found}")
        self.mem("ldr", "x0", self.slot_off(i))
        self.emit("add  x0, x0, #1")
        self.mem("str", "x0", self.slot_off(i))
        self.emit(f"b    {top}")
        self.label(found)
        self.emit("mov  x0, #1")
        self.emit(f"b    {end + 'x'}")
        self.label(end)
        self.emit("mov  x0, #0")
        self.label(end + "x")

    # ---- impresión ----------------------------------------------------------------
    def visit_Println(self, e):
        self.comment(unparse(e).replace("(...)", "") + " ...")
        args = e.args
        ai = 0
        for seg in e.fmt or []:
            if seg[0] == "text":
                self.load_str(seg[1])
                self.load_int("x1", len(seg[1].encode("utf-8")))
                self.rt("_out_write")
                continue
            if seg[0] == "value":
                a, debug, prec = args[0], False, None
            else:
                a = args[1 + ai] if ai + 1 < len(args) else None
                if a is None:
                    continue
                debug, prec = seg[1], seg[2]
                ai += 1
            self.gen(a)
            self.emit_print(a.type, debug, prec)
        if e.newline:
            self.rt("_print_nl")

    def emit_print(self, t, debug=False, prec=None):
        """Imprime el valor de x0/d0 según su tipo estático."""
        k = t.kind
        if k == "none":
            self.load_str("None")
            self.rt("_print_str")
        elif k == "i32":
            self.rt("_print_int")
        elif k == "f64":
            if prec is not None:
                self.load_int("x0", prec)
                self.rt("_print_f64p")
            else:
                self.rt("_print_f64")
        elif k == "bool":
            self.rt("_print_bool")
        elif k == "char":
            self.rt("_print_qchar" if debug else "_print_char")
        elif k == "String":
            self.rt("_print_qstr" if debug else "_print_str")
        elif t.is_seq:
            lab = self.array_printer(t)
            if t.kind == "vec":
                self.emit("ldr  x1, [x0, #-8]")
            else:
                self.load_int("x1", t.n)
            self.emit(f"bl   {lab}")
        else:
            self.load_str("()")
            self.rt("_print_str")

    def array_printer(self, t):
        key = str(t)
        if key in self.helpers:
            return self.helpers[key]
        lab = f"_pa_{len(self.helpers)}"
        self.helpers[key] = lab
        saved = self.lines
        self.lines = []
        self.used.update({"_out_byte"})
        et = t.elem
        loop, nocomma, done = lab + "_loop", lab + "_nc", lab + "_done"
        self.raw(f"// imprime un arreglo de tipo {t}: x0 = datos, x1 = cantidad de elementos")
        self.raw(f"{lab}:")
        self.emit("stp  x29, x30, [sp, #-48]!")
        self.emit("mov  x29, sp")
        self.emit("stp  x19, x20, [sp, #16]")
        self.emit("str  x21, [sp, #32]")
        self.emit("mov  x19, x0")
        self.emit("mov  x20, x1")
        self.emit("mov  x21, #0")
        self.emit("mov  w0, #91")
        self.rt("_out_byte")
        self.label(loop)
        self.emit("cmp  x21, x20")
        self.emit(f"b.hs {done}")
        self.emit(f"cbz  x21, {nocomma}")
        self.emit("mov  w0, #44")
        self.rt("_out_byte")
        self.emit("mov  w0, #32")
        self.rt("_out_byte")
        self.label(nocomma)
        if et.is_aggregate:
            self.load_int("x0", et.byte_size())
            self.emit("madd x0, x21, x0, x19")
        elif et == T.F64:
            self.emit("ldr  d0, [x19, x21, lsl #3]")
        else:
            self.emit("ldr  x0, [x19, x21, lsl #3]")
        self.emit_print(et, True)
        self.emit("add  x21, x21, #1")
        self.emit(f"b    {loop}")
        self.label(done)
        self.emit("mov  w0, #93")
        self.rt("_out_byte")
        self.emit("ldp  x19, x20, [sp, #16]")
        self.emit("ldr  x21, [sp, #32]")
        self.emit("ldp  x29, x30, [sp], #48")
        self.emit("ret")
        self.raw("")
        self.helper_code.extend(self.lines)
        self.lines = saved
        return lab


def generate(program, table):
    return CodeGenerator(program, table).generate()
