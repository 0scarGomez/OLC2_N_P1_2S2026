(() => {
  const $ = (id) => document.getElementById(id);
  const code = $("code"), gutter = $("gutter"), consoleEl = $("console"), asmEl = $("asm");
  const DEFAULT = `fn main() {
    let x: i32 = 10;
    let mut y: i32 = 20;

    if x < y {
        y = y - x;
    } else {
        y = y + x;
    }

    let mut i = 0;
    while i < 3 {
        println!("i = {}", i);
        i += 1;
    }
    println!("x = {}, y = {}", x, y);
}
`;
  let errorLines = new Set();
  let fileName = "sin_titulo.og";

  // ---------- editor ----------
  function renderGutter() {
    const n = code.value.split("\n").length;
    let h = "";
    for (let i = 1; i <= n; i++) h += (errorLines.has(i) ? `<span class="err">${i}</span>` : i) + "\n";
    gutter.innerHTML = h;
    gutter.scrollTop = code.scrollTop;
  }
  function updateCursor() {
    const pos = code.selectionStart, before = code.value.slice(0, pos).split("\n");
    $("cursor").textContent = `Ln ${before.length}, Col ${before[before.length - 1].length + 1}`;
  }
  code.addEventListener("input", () => { errorLines = new Set(); renderGutter(); });
  code.addEventListener("scroll", () => (gutter.scrollTop = code.scrollTop));
  code.addEventListener("keyup", updateCursor);
  code.addEventListener("click", updateCursor);
  code.addEventListener("keydown", (e) => {
    if (e.key === "Tab") {
      e.preventDefault();
      const s = code.selectionStart;
      code.setRangeText("    ", s, code.selectionEnd, "end");
      renderGutter();
    } else if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault(); run();
    }
  });
  const setCode = (text, name) => { code.value = text; fileName = name || fileName; $("file-name").textContent = fileName; errorLines = new Set(); renderGutter(); updateCursor(); };

  // ---------- archivo ----------
  $("btn-new").onclick = () => { if (!code.value.trim() || confirm("¿Descartar el contenido actual?")) setCode(DEFAULT, "sin_titulo.og"); };
  $("btn-open").onclick = () => $("file-input").click();
  $("file-input").onchange = async (e) => {
    const f = e.target.files[0]; if (!f) return;
    setCode(await f.text(), f.name); e.target.value = "";
  };
  $("btn-save").onclick = () => {
    const blob = new Blob([code.value], { type: "text/plain;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = fileName.endsWith(".og") ? fileName : fileName + ".og";
    a.click(); URL.revokeObjectURL(a.href);
  };
  $("examples").onchange = async (e) => {
    if (!e.target.value) return;
    const r = await fetch("/api/example/" + e.target.value);
    const d = await r.json(); setCode(d.code, d.name + ".og"); e.target.value = "";
  };

  // ---------- reportes ----------
  $("btn-reports").onclick = (e) => { e.stopPropagation(); $("reports-menu").hidden = !$("reports-menu").hidden; };
  document.addEventListener("click", () => ($("reports-menu").hidden = true));
  document.querySelectorAll(".tab").forEach((t) => (t.onclick = () => showTab(t.dataset.tab)));
  function showTab(name) {
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
    ["errors", "symbols", "ast"].forEach((n) => ($("tab-" + n).hidden = n !== name));
  }
  let zoom = 1;
  const applyZoom = () => { const s = $("ast-view").querySelector("svg"); if (s) s.style.transform = `scale(${zoom})`; };
  $("z-in").onclick = () => { zoom = Math.min(zoom * 1.25, 4); applyZoom(); };
  $("z-out").onclick = () => { zoom = Math.max(zoom / 1.25, 0.1); applyZoom(); };
  $("z-fit").onclick = () => {
    const s = $("ast-view").querySelector("svg"); if (!s) return;
    s.style.transform = "scale(1)";
    const w = s.getBoundingClientRect().width, avail = $("ast-view").clientWidth - 8;
    zoom = Math.min(1, avail / w); applyZoom();
  };

  // ---------- ARM64 con color ----------
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  function colorAsm(text) {
    return text.split("\n").map((l) => {
      const e = esc(l);
      if (/^\s*\/\//.test(l)) return `<span class="c">${e}</span>`;
      if (/^[.\w$]+:/.test(l)) return `<span class="l">${e}</span>`;
      if (/^\./.test(l) || /^\s*\.(asciz|quad|skip|balign)/.test(l)) return `<span class="d">${e}</span>`;
      return e.replace(/^(\s+)([a-z0-9.]+)/, '$1<span class="i">$2</span>').replace(/(\/\/.*)$/, '<span class="c">$1</span>');
    }).join("\n");
  }

  // ---------- ejecutar ----------
  const out = (cls, text) => { consoleEl.insertAdjacentHTML("beforeend", `<span class="${cls}">${esc(text)}</span>`); };
  async function run() {
    const btn = $("btn-run"); btn.disabled = true;
    consoleEl.innerHTML = "";
    out("h", "> Ejecutando OxigenNative...\n");
    let d;
    try {
      const r = await fetch("/api/compile", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: code.value, run: true }) });
      d = await r.json();
    } catch (err) { out("e", "No se pudo contactar al servidor: " + err + "\n"); btn.disabled = false; return; }
    btn.disabled = false;

    errorLines = new Set(d.errors.map((e) => e.linea)); renderGutter();
    if (d.errors.length) { out("e", d.errors_text + "\n\n"); }
    if (d.generated) out("s", "Compilación exitosa" + (d.errors.length ? " (con errores recuperables).\n" : ".\n"));
    else out("e", (d.message || "No se generó código.") + "\n");
    if (d.generated && d.executed) {
      out("h", "—— Programa en ejecución ——\n");
      out("", d.stdout.endsWith("\n") || !d.stdout ? d.stdout : d.stdout + "\n");
      if (d.stderr) out("e", d.stderr);
      out("h", "—— Fin de la ejecución ——\n");
      out("", `Código de salida: ${d.returncode} · Tiempo de ejecución: ${d.seconds}s\n`);
    } else if (d.generated) { out("e", d.message + "\n"); if (d.stdout) out("", d.stdout + "\n"); }

    asmEl.innerHTML = d.asm ? colorAsm(d.asm) : '<span class="muted">No se generó código ARM64.</span>';
    $("asm-info").textContent = d.asm ? `${d.asm.split("\n").length} líneas` : "";
    $("tab-errors").innerHTML = d.errors_html;
    $("tab-symbols").innerHTML = d.symbols_html;
    $("ast-view").innerHTML = d.ast_svg || '<p class="muted center">No hay AST disponible.</p>';
    zoom = 1; applyZoom();
    const b = $("badge-errors"); b.textContent = d.errors.length; b.classList.toggle("zero", !d.errors.length);
    showTab(d.errors.length ? "errors" : "symbols");
    consoleEl.scrollTop = consoleEl.scrollHeight;
  }
  $("btn-run").onclick = run;
  $("btn-clear").onclick = () => (consoleEl.innerHTML = "");

  setCode(DEFAULT, fileName);
})();
