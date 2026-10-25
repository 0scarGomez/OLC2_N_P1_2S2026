"""Reportes: tabla de errores (HTML), tabla de símbolos (HTML) y AST (Graphviz DOT/SVG/PNG)."""

import html
import os
import shutil
import subprocess

from . import ast_nodes as A

STYLE = """
body{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#1b2430}
h1{font-size:20px;margin:0 0 4px} p.sub{color:#5b6778;margin:0 0 16px;font-size:13px}
table{border-collapse:collapse;width:100%;font-size:14px}
th{background:#3b7ddd;color:#fff;text-align:left;padding:8px 10px}
td{border:1px solid #cfd8e3;padding:7px 10px;vertical-align:top}
tr:nth-child(even) td{background:#f5f8fc} code{font-family:Consolas,monospace;background:#eef2f7;padding:1px 4px;border-radius:3px}
.k-Léxico{color:#b45309;font-weight:600}.k-Sintáctico{color:#b91c1c;font-weight:600}.k-Semántico{color:#6d28d9;font-weight:600}
.ok{color:#15803d;font-weight:600}
"""


def _page(title, subtitle, body):
    return (f"<!doctype html><html lang='es'><head><meta charset='utf-8'><title>{html.escape(title)}</title>"
            f"<style>{STYLE}</style></head><body><h1>{html.escape(title)}</h1>"
            f"<p class='sub'>{html.escape(subtitle)}</p>{body}</body></html>")


def errors_table(rows):
    if not rows:
        return "<p class='ok'>✔ No se detectaron errores.</p>"
    out = ["<table><thead><tr><th>No</th><th>Tipo</th><th>Descripción</th><th>Línea</th>"
           "<th>Columna</th><th>Fragmento</th></tr></thead><tbody>"]
    for r in rows:
        out.append(
            f"<tr><td>{r['no']}</td><td class='k-{r['tipo']}'>{r['tipo']}</td>"
            f"<td>{html.escape(r['descripcion'])}</td><td>{r['linea']}</td><td>{r['columna']}</td>"
            f"<td><code>{html.escape(r['fragmento'])}</code></td></tr>")
    out.append("</tbody></table>")
    return "".join(out)


def symbols_table(rows):
    if not rows:
        return "<p>No hay símbolos registrados.</p>"
    out = ["<table><thead><tr><th>No.</th><th>Identificador</th><th>Categoría</th><th>Tipo</th>"
           "<th>Ámbito</th><th>Línea</th><th>Valor</th></tr></thead><tbody>"]
    for r in rows:
        name = html.escape(r["identificador"]) + (" <small>(mut)</small>" if r.get("mutable") else "")
        out.append(
            f"<tr><td>{r['no']}</td><td><code>{name}</code></td><td>{r['categoria']}</td>"
            f"<td><code>{html.escape(r['tipo'])}</code></td><td>{html.escape(r['ambito'])}</td>"
            f"<td>{r['linea']}</td><td><code>{html.escape(str(r['valor']))}</code></td></tr>")
    out.append("</tbody></table>")
    return "".join(out)


def errors_html(rows):
    return _page("Reporte de errores", f"OxigenNative · {len(rows)} error(es)", errors_table(rows))


def symbols_html(rows):
    return _page("Reporte de la tabla de símbolos", f"OxigenNative · {len(rows)} símbolo(s)", symbols_table(rows))


# ---------------------------------------------------------------------------
# AST -> Graphviz
# ---------------------------------------------------------------------------
def _q(s):
    return str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _literal_text(n):
    if n.kind == "String":
        return '"' + n.value.replace("\n", "\\n") + '"'
    if n.kind == "char":
        return "'" + n.value.replace("\n", "\\n") + "'"
    if n.kind == "bool":
        return "true" if n.value else "false"
    return str(n.value)


def describe(n):
    """(etiqueta, lista de hijos) de cada nodo para el gráfico del AST."""
    C = n.__class__.__name__
    if isinstance(n, A.Program):
        return "Program", n.items
    if isinstance(n, A.Function):
        ret = f" -> {n.ret_type}" if n.ret_type else ""
        return f"Function\n{n.name}{ret}", list(n.params) + list(n.body.stmts)
    if isinstance(n, A.Param):
        return f"Param\n{n.name}: {n.ptype}", []
    if isinstance(n, A.Block):
        return "Block", n.stmts
    if isinstance(n, A.VarDecl):
        ident = A.Identifier(n.name)
        kind = "let mut" if n.mutable else "let"
        ann = f": {n.type_ann}" if n.type_ann else ""
        ch = [ident] + ([n.init] if n.init is not None else [])
        return f"VariableDeclaration\n{kind}{ann}", ch
    if isinstance(n, A.Assign):
        return f"Assignment\n{n.op}", [n.target, n.value]
    if isinstance(n, A.ExprStmt):
        return "ExprStmt", [n.expr]
    if isinstance(n, A.If):
        ch = [n.cond, n.then] + ([n.else_] if n.else_ is not None else [])
        return "If", ch
    if isinstance(n, A.While):
        return "While" + (f"\n{n.label}" if n.label else ""), [n.cond, n.body]
    if isinstance(n, A.Loop):
        return "Loop" + (f"\n{n.label}" if n.label else ""), [n.body]
    if isinstance(n, A.For):
        return f"For\n{n.var}", [n.iterable, n.body]
    if isinstance(n, A.Match):
        return "Match", [n.subject] + list(n.arms)
    if isinstance(n, A.MatchArm):
        return "MatchArm", list(n.patterns) + [n.body]
    if isinstance(n, A.Wildcard):
        return "Wildcard\n_", []
    if isinstance(n, A.Break):
        return "Break" + (f"\n{n.label}" if n.label else ""), []
    if isinstance(n, A.Continue):
        return "Continue" + (f"\n{n.label}" if n.label else ""), []
    if isinstance(n, A.Return):
        return "Return", [n.value] if n.value is not None else []
    if isinstance(n, A.Literal):
        return f"Literal\n{_literal_text(n)}", []
    if isinstance(n, A.Identifier):
        return f"Identifier\n{n.name}", []
    if isinstance(n, A.Binary):
        return f"BinaryOp\n{n.op}", [n.left, n.right]
    if isinstance(n, A.Unary):
        return f"UnaryOp\n{n.op}", [n.operand]
    if isinstance(n, A.Cast):
        return f"Cast\nas {n.target}", [n.expr]
    if isinstance(n, A.Call):
        return f"Call\n{n.name}", n.args
    if isinstance(n, A.MethodCall):
        return f"MethodCall\n.{n.name}", [n.obj] + list(n.args)
    if isinstance(n, A.StaticCall):
        return f"StaticCall\n{n.owner}::{n.name}", n.args
    if isinstance(n, A.Index):
        return "Index", [n.base, n.index]
    if isinstance(n, A.Range):
        return "Range\n" + ("..=" if n.inclusive else ".."), [n.lo, n.hi]
    if isinstance(n, A.SliceExpr):
        return "Slice", [n.base, n.lo_node, n.hi_node]
    if isinstance(n, A.ArrayLit):
        return "ArrayLiteral", n.elems
    if isinstance(n, A.ArrayRepeat):
        return f"ArrayRepeat\n; {n.count}", [n.elem]
    if isinstance(n, A.StructDecl):
        return f"StructDecl\n{n.name}", list(n.fields)
    if isinstance(n, A.StructLit):
        return f"StructLiteral\n{n.name}", [v for _, v, _, _ in n.inits]
    if isinstance(n, A.FieldAccess):
        return f"FieldAccess\n.{n.name}", [n.base]
    if isinstance(n, A.Println):
        return ("Println" if n.newline else "Print"), n.args
    return C, n.children()


SHAPES = {
    "Program": "#dbeafe", "Function": "#dcfce7", "VariableDeclaration": "#fef9c3",
    "Println": "#fce7f3", "Print": "#fce7f3", "If": "#ede9fe", "While": "#ede9fe",
    "Loop": "#ede9fe", "For": "#ede9fe", "Match": "#ede9fe",
}


def ast_dot(program):
    lines = ["digraph AST {", '  rankdir=TB;',
             '  node [shape=box, fontname="Helvetica", fontsize=11, style="filled", fillcolor="#ffffff"];',
             '  edge [color="#475569"];']
    counter = [0]

    def walk(n):
        counter[0] += 1
        me = f"n{counter[0]}"
        label, kids = describe(n)
        color = SHAPES.get(label.split("\n")[0], "#ffffff")
        lines.append(f'  {me} [label="{_q(label)}", fillcolor="{color}"];')
        for k in kids:
            if k is None:
                continue
            kid = walk(k)
            lines.append(f"  {me} -> {kid};")
        return me

    if program is not None:
        walk(program)
    lines.append("}")
    return "\n".join(lines)


def render_dot(dot_text, fmt, path):
    exe = shutil.which("dot")
    if not exe:
        return False
    p = subprocess.run([exe, f"-T{fmt}", "-o", path], input=dot_text.encode("utf-8"), capture_output=True)
    return p.returncode == 0


def write_reports(result, outdir):
    """Genera en `outdir` errores.html, simbolos.html, ast.dot, ast.svg y ast.png."""
    os.makedirs(outdir, exist_ok=True)
    err_rows = result.errors.to_list() if result.errors is not None else []
    sym_rows = result.table.report_rows() if result.table is not None else []
    files = {}
    with open(os.path.join(outdir, "errores.html"), "w", encoding="utf-8") as f:
        f.write(errors_html(err_rows))
    files["errores.html"] = True
    with open(os.path.join(outdir, "simbolos.html"), "w", encoding="utf-8") as f:
        f.write(symbols_html(sym_rows))
    files["simbolos.html"] = True
    dot = ast_dot(result.ast)
    with open(os.path.join(outdir, "ast.dot"), "w", encoding="utf-8") as f:
        f.write(dot)
    files["ast.dot"] = True
    for fmt in ("svg", "png"):
        files[f"ast.{fmt}"] = render_dot(dot, fmt, os.path.join(outdir, f"ast.{fmt}"))
    return files, err_rows, sym_rows, dot
