
Intérprete del lenguaje académico **OxigenScript** (sintaxis inspirada en
Rust), desarrollado para el Proyecto 1 del curso Organización de Lenguajes
y Compiladores 2 (USAC).

- Análisis léxico y sintáctico con **PLY (Python Lex-Yacc)**.
- Construcción de un **AST** propio (`backend/analizador/ast_nodes.py`).
- Análisis semántico y ejecución combinados en una sola pasada (intérprete
  de árbol), con manejo resiliente de errores.
- Generación de reportes: **errores**, **tabla de símbolos** (HTML) y
  **AST** (DOT + PNG/PDF/SVG vía Graphviz).
- Interfaz web (Flask + HTML/Bootstrap/JS) tipo IDE simple: editor con
  numeración de líneas, consola de salida y pestañas de reportes.

## Documentación

- [`documentacion/MANUAL_USUARIO.md`](docs/MANUAL_USUARIO.md) — cómo instalar,
  ejecutar y usar la herramienta, con capturas de pantalla e instrucciones
  para interpretar cada reporte.
- [`documentacion/DOCUMENTACION_TECNICA.md`](docs/DOCUMENTACION_TECNICA.md) —
  arquitectura, gramática formal, estrategia de interpretación, decisiones
  de diseño y desafíos enfrentados.

## Inicio rápido

```bash
pip install -r requirements.txt
python3 app.py
# abrir http://127.0.0.1:5000
```

## Estructura del proyecto

```
OLC2_N_P1_2S2026/
├── app.py                          # Servidor Flask + endpoint /ejecutar
├── main.py                         # Script de prueba por consola
├── backend/analizador/
│   ├── lexer.py                    # Análisis léxico (PLY lex)
│   ├── parser.py                   # Análisis sintáctico (PLY yacc) → AST
│   ├── ast_nodes.py                # Nodos del AST (semántica + ejecución)
│   └── tabla_simbolos.py           # Entorno / Símbolo (ámbitos anidados)
├── templates/index.html            # Interfaz web (editor + reportes)
├── docs/                           # Documentación técnica y manual de usuario
│   ├── DOCUMENTACION_TECNICA.md
│   ├── MANUAL_USUARIO.md
│   └── img/
├── reporte_simbolos.html           # Generado en cada ejecución
└── reporte_ast.{dot,png,pdf,svg}   # Generado en cada ejecución
```
