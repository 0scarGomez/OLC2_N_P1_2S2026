"""Ensamblado, enlace y ejecución del código ARM64 generado"""

import os
import platform
import shutil
import subprocess
import tempfile
import time

TIMEOUT = 10  # segundos de ejecución permitidos
MAX_OUTPUT = 2_000_000


def _which(*names):
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None


def find_tools():
    native = platform.machine().lower() in ("aarch64", "arm64")
    asm = _which("aarch64-linux-gnu-as", *(("as",) if native else ()))
    ld = _which("aarch64-linux-gnu-ld", *(("ld",) if native else ()))
    qemu = None if native else _which("qemu-aarch64", "qemu-aarch64-static")
    return asm, ld, qemu, native


def assemble_and_run(asm_text, workdir=None, timeout=TIMEOUT):
    """Devuelve dict: ok, stage, stdout, stderr, returncode, seconds, message."""
    asm, ld, qemu, native = find_tools()
    res = {"ok": False, "stage": "", "stdout": "", "stderr": "", "returncode": None,
           "seconds": 0.0, "message": ""}
    if not asm or not ld or (not native and not qemu):
        missing = [n for n, v in (("aarch64-linux-gnu-as", asm), ("aarch64-linux-gnu-ld", ld),
                                  ("qemu-aarch64", qemu if not native else True)) if not v]
        res["stage"] = "herramientas"
        res["message"] = "Faltan herramientas: " + ", ".join(missing)
        return res
    tmp = workdir or tempfile.mkdtemp(prefix="oxigen_")
    s_path, o_path, exe = (os.path.join(tmp, n) for n in ("programa.s", "programa.o", "programa"))
    with open(s_path, "w", encoding="utf-8") as f:
        f.write(asm_text)
    p = subprocess.run([asm, "-o", o_path, s_path], capture_output=True, text=True)
    if p.returncode != 0:
        res.update(stage="ensamblado", stderr=p.stderr, message="Error al ensamblar el código ARM64.")
        return res
    p = subprocess.run([ld, "-o", exe, o_path], capture_output=True, text=True)
    if p.returncode != 0:
        res.update(stage="enlace", stderr=p.stderr, message="Error al enlazar el ejecutable.")
        return res
    cmd = [exe] if native else [qemu, exe]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout)
        res["seconds"] = time.time() - t0
        res.update(ok=True, stage="ejecución", returncode=p.returncode,
                   stdout=p.stdout[:MAX_OUTPUT].decode("utf-8", "replace"),
                   stderr=p.stderr[:MAX_OUTPUT].decode("utf-8", "replace"))
    except subprocess.TimeoutExpired as ex:
        res["seconds"] = time.time() - t0
        res.update(ok=False, stage="ejecución",
                   stdout=(ex.stdout or b"")[:MAX_OUTPUT].decode("utf-8", "replace"),
                   message=f"Tiempo de ejecución excedido ({timeout}s). Posible ciclo infinito.")
    return res
