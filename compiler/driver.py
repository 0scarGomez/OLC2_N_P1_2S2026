"""Pipeline completo: léxico -> sintáctico -> semántico -> ARM64 -> ensamblar -> QEMU."""

import threading

from . import codegen, toolchain
from .errors import ErrorList
from .parser import OxigenParser
from .semantic import SemanticAnalyzer

_lock = threading.Lock()


class CompileResult:
    def __init__(self):
        self.errors = None
        self.ast = None
        self.table = None
        self.asm = ""
        self.run = None
        self.generated = False


def compile_source(source, execute=True, workdir=None):
    with _lock:
        r = CompileResult()
        r.errors = ErrorList(source)
        parser = OxigenParser(r.errors)
        r.ast = parser.parse(source)
        if r.ast is not None and not r.errors.fatal:
            sem = SemanticAnalyzer(r.errors)
            r.table = sem.analyze(r.ast)
        if r.ast is not None and r.table is not None and not r.errors.fatal:
            r.asm = codegen.generate(r.ast, r.table)
            r.generated = True
            if execute:
                r.run = toolchain.assemble_and_run(r.asm, workdir)
        return r
