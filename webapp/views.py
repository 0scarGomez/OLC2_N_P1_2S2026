"""Capa de servicios (API REST JSON) del compilador OxigenNative."""

import json
import os
import re
import time
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from compiler.driver import compile_source
from compiler.reports import errors_table, symbols_table, write_reports

EXAMPLES = Path(settings.BASE_DIR) / "tests" / "examples"
REPORT_FILES = {
    "errores.html": "text/html", "simbolos.html": "text/html", "ast.dot": "text/plain",
    "ast.svg": "image/svg+xml", "ast.png": "image/png", "programa.s": "text/plain",
}


def index(request):
    examples = sorted(p.stem for p in EXAMPLES.glob("*.og"))
    return render(request, "webapp/index.html", {"examples": examples})


@require_POST
def api_compile(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "JSON inválido"}, status=400)
    code = data.get("code", "")
    execute = bool(data.get("run", True))
    t0 = time.time()
    res = compile_source(code, execute=execute)
    outdir = Path(settings.REPORTS_DIR) / "ultima_ejecucion"
    files, err_rows, sym_rows, dot = write_reports(res, outdir)
    if res.asm:
        (outdir / "programa.s").write_text(res.asm, encoding="utf-8")
    svg = ""
    svg_path = outdir / "ast.svg"
    if files.get("ast.svg") and svg_path.exists():
        svg = svg_path.read_text(encoding="utf-8")
        svg = re.sub(r"^.*?<svg", "<svg", svg, count=1, flags=re.S)

    out = {
        "errors": err_rows,
        "errors_text": res.errors.format_all(),
        "errors_html": errors_table(err_rows),
        "symbols_html": symbols_table(sym_rows),
        "ast_svg": svg,
        "ast_dot": dot,
        "asm": res.asm,
        "generated": res.generated,
        "executed": bool(res.run and res.run.get("ok")),
        "stdout": "", "stderr": "", "returncode": None, "message": "",
        "seconds": 0.0, "total_seconds": round(time.time() - t0, 3),
        "reports": files,
    }
    if res.run:
        out.update(stdout=res.run["stdout"], stderr=res.run["stderr"],
                   returncode=res.run["returncode"], message=res.run["message"] or res.run["stderr"]
                   if not res.run["ok"] else "", seconds=round(res.run["seconds"], 4))
    elif not res.generated:
        out["message"] = "No se generó código: corrige los errores críticos reportados."
    return JsonResponse(out)


def api_example(request, name):
    path = EXAMPLES / f"{os.path.basename(name)}.og"
    if not path.exists():
        raise Http404
    return JsonResponse({"name": name, "code": path.read_text(encoding="utf-8")})


def download_report(request, name):
    if name not in REPORT_FILES:
        raise Http404
    path = Path(settings.REPORTS_DIR) / "ultima_ejecucion" / name
    if not path.exists():
        raise Http404("Aún no hay reportes: ejecuta un programa primero.")
    resp = FileResponse(open(path, "rb"), content_type=REPORT_FILES[name])
    if request.GET.get("download"):
        resp["Content-Disposition"] = f'attachment; filename="{name}"'
    return resp
