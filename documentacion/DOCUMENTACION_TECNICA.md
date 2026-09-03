# Documentación Técnica — OxigenScript


---

## 1. Arquitectura general

El proyecto sigue la arquitectura monolítica cliente/servidor propuesta en el
enunciado, implementada con **Flask** + **PLY (Python Lex-Yacc)**:

```
Navegador (templates/index.html)
        │  fetch('/ejecutar', { codigo })
        ▼
   app.py  (Flask)
        │
        ├── backend/analizador/lexer.py    → Análisis léxico (PLY lex)
        ├── backend/analizador/parser.py   → Análisis sintáctico (PLY yacc) → AST
        ├── backend/analizador/ast_nodes.py→ Nodos del AST + método ejecutar()
        │                                    (análisis semántico + interpretación)
        └── backend/analizador/tabla_simbolos.py → Entorno / Símbolo (ámbitos)
        │
        ├── generar_reporte_simbolos_html()  → reporte_simbolos.html
        └── generar_dot_ast() + dot (CLI)    → reporte_ast.dot/.png/.pdf/.svg
```

- **Presentación**: `templates/index.html`, servido por Flask (`/`). Contiene el
  editor de código, la consola de salida y el panel de reportes con pestañas
  (Bootstrap 5 + JavaScript embebido).
- **Lógica/Servicios**: `app.py` expone el endpoint `POST /ejecutar`, que
  recibe `{ "codigo": "<fuente>" }`, ejecuta el pipeline completo y responde
  un JSON con la consola, los errores, la tabla de símbolos y el AST (en
  formato DOT y SVG).
- **Definición del lenguaje**: la gramática de OxigenScript, implementada con
  PLY en `lexer.py` (tokens) y `parser.py` (reglas de producción → AST).

## 2. Flujo de ejecución (`app.py` → `/ejecutar`)

1. Se limpian las listas globales `errores_lexicos` y `errores_sintacticos`.
2. Se redirige `sys.stdout` a un buffer en memoria (`io.StringIO`), porque
   la sentencia `Imprimir` del lenguaje usa `print()` de Python internamente;
   esto permite capturar la salida del programa OxigenScript sin mezclarla
   con los logs del servidor.
3. Se tokeniza y parsea el código: `parser.parse(codigo, lexer=lexer)` →
   produce una lista de nodos AST (`init : instrucciones`).
4. Si el AST no es `None`:
   - Se crea el ámbito raíz `Entorno(nombre_ambito="Global")`.
   - Se ejecutan todas las instrucciones de nivel superior (esto registra
     funciones y variables globales, incluida la función `main`).
   - Se busca el símbolo `main` en el entorno global y, si es de categoría
     `Funcion`, se invoca automáticamente construyendo una `LlamadaFuncion`
     sintética (`main()`), replicando la sentencia "el intérprete localiza
     la función principal y la ejecuta" del enunciado.
   - Se recolecta la lista de símbolos (`entorno_global.todos_los_simbolos`)
     para el reporte de tabla de símbolos.
   - Se generan los reportes: HTML de símbolos, y DOT/PNG/PDF/SVG del AST
     (usando el binario `dot` de Graphviz vía `subprocess`).
5. Se responde un JSON con `exito`, `consola`, `simbolos`, `errores`,
   `ast_dot` y `ast_svg`.
6. Si el AST es `None` (error léxico/sintáctico bloqueante), se responde con
   `exito: false` y la lista de errores léxicos/sintácticos acumulada.

## 3. Analizador léxico (`lexer.py`)

Construido con `ply.lex`. Aspectos relevantes:

- **Palabras reservadas** (`reservadas`): `fn, let, mut, if, else, while,
  loop, match, break, continue, return, struct, true, false, i32, f64, bool,
  char, String, println`.
- **Literales**: `ENTERO` (`\d+`), `DECIMAL` (`\d+\.\d+`), `CADENA` (con
  soporte de escapes `\n \t \r \" \\`), `CARACTER` (`'x'`), y **raw strings**
  `r"..."` / `r#"..."#`.
- **Comentarios**: de línea (`//...`) y de bloque (`/* ... */`), con
  detección de bloque **sin cerrar** como error léxico (`t_COMENTARIO_MULTILINEA`).
- **Etiquetas de loop** (`t_ETIQUETA`): `'nombre` (para `'outer: loop { ... }`),
  distinguibles de `CARACTER` porque este último exige comilla de cierre.
- **Manejo de errores léxicos** (`t_error`): cada carácter no reconocido se
  agrega a la lista global `errores_lexicos` con línea y columna, y el lexer
  descarta el carácter (`t.lexer.skip(1)`) y continúa, en vez de detenerse.

## 4. Analizador sintáctico (`parser.py`)

Construido con `ply.yacc` (`write_tables=False`), gramática LALR que produce
directamente instancias de los nodos definidos en `ast_nodes.py`.

###  Precedencia de operadores

```python
precedence = (
    ('left', 'OR'),
    ('left', 'AND'),
    ('left', 'IGUAL_IGUAL', 'DIFERENTE'),
    ('left', 'MAYOR_QUE', 'MENOR_QUE', 'MAYOR_IGUAL', 'MENOR_IGUAL'),
    ('left', 'MAS', 'MENOS'),
    ('left', 'POR', 'DIV', 'MOD'),
    ('right', 'NOT', 'UMENOS'),
    ('left', 'PUNTO'),
    ('left', 'PAR_IZQ'),
)
```

###  Gramática formal (resumen en notación BNF)

```
init                 ::= instrucciones

instrucciones        ::= instrucciones instruccion | instruccion

instruccion          ::= declaracion_variable
                        | asignacion
                        | imprimir
                        | if_stmt | while_stmt | loop_stmt | match_stmt
                        | break_stmt | continue_stmt | return_stmt
                        | funcion_decl | struct_decl
                        | asignacion_arreglo | asignacion_atributo
                        | expresion ';'
                        | metodo_suelto ';'
                        | bloque

declaracion_variable ::= 'let' ['mut'] ID ':' tipo '=' expresion ';'
                        | 'let' ['mut'] ID '=' expresion ';'
                        | 'let' ['mut'] ID ':' tipo ';'

asignacion            ::= ID ('=' | '+=' | '-=' | '*=' | '/=' | '%=') expresion ';'

imprimir               ::= 'println' '!'? '(' argumentos ')' ';'

if_stmt                ::= 'if' expresion bloque ['else' (bloque | if_stmt)]
while_stmt              ::= 'while' expresion bloque
loop_stmt               ::= ['ETIQUETA' ':'] 'loop' bloque
break_stmt              ::= 'break' ['ETIQUETA'] ';'
continue_stmt           ::= 'continue' ['ETIQUETA'] ';'
return_stmt             ::= 'return' [expresion] ';'

funcion_decl            ::= 'fn' ID '(' [parametros] ')' ['->' tipo] bloque
parametros              ::= parametro (',' parametro)*
parametro               ::= ID ':' tipo

struct_decl             ::= 'struct' ID '{' campo (',' campo)* [','] '}'
campo                   ::= ID ':' tipo

match_stmt              ::= 'match' expresion '{' caso (',')? ... '}'
caso                    ::= expresion '=>' (bloque | expresion)

bloque                  ::= '{' instrucciones '}' | '{' '}'

tipo                    ::= 'i32' | 'f64' | 'bool' | 'String' | 'char'
                          | '[' tipo ']'
                          | '[' tipo ';' ENTERO ']'
                          | ID                       -- (tipo struct)
                          | ID '<' '&' ID '>'

expresion               ::= ID '{' campo_valor (',' campo_valor)* '}'   -- InstanciacionStruct
                          | expresion_base

expresion_base           ::= ENTERO | DECIMAL | CADENA | CARACTER | 'true' | 'false'
                          | ID
                          | expresion_base OP expresion_base    -- OP: + - * / % > < >= <= == != && || &
                          | expresion_base '[' expresion ']'                       -- índice de arreglo
                          | expresion_base '.' ID                                  -- acceso a atributo
                          | expresion_base '.' ID '(' [argumentos] ')'             -- llamada a método
                          | ('String' | ID) '::' ID '(' [expresion_base] ')'       -- String::from / ::new
                          | ID '(' [argumentos] ')'                                -- llamada a función
                          | '[' [elementos] ']'                                    -- arreglo literal
                          | '[' expresion ';' expresion ']'                        -- arreglo por repetición
                          | '&' expresion_base '[' expresion '..' expresion ']'    -- slice
                          | '-' expresion_base  | '!' expresion_base               -- unarios
                          | '(' expresion_base ')'

argumentos               ::= expresion (',' expresion)*
elementos                ::= expresion (',' expresion)*
```

> **Nota:** por simplicidad de la gramática, las condiciones de `if`,
> `while` y `match` usan la producción `expresion_sin_struct` (que excluye
> la instanciación de structs) para evitar la ambigüedad clásica de Rust
> entre `if cond { ... }` y un literal de struct `Nombre { ... }`, ya que el
> lenguaje no exige paréntesis alrededor de la condición.

###  Recuperación de errores sintácticos

`p_error(p)` registra el error en `errores_sintacticos` (tipo, descripción,
línea, columna) y llama a `parser.errok()`, lo que le indica a PLY que
descarte el token conflictivo y continúe el análisis en modo de recuperación
de errores en lugar de abortar de inmediato, permitiendo detectar más de un
error sintáctico por ejecución.

## 5. AST y análisis semántico + ejecución (`ast_nodes.py`)

Cada construcción del lenguaje es una clase que hereda de `Instruccion` o
`Expresion` (ambas heredan de `NodoAST`, que guarda `linea`/`columna`).
**No existe una fase de análisis semántico separada**: cada nodo implementa
un método `ejecutar(entorno)` que en una sola pasada:

1. Evalúa recursivamente sus sub-nodos.
2. Valida tipos/reglas semánticas antes de operar.
3. Ejecuta la operación y devuelve un `ResultadoObtenido(valor, tipo)`
   (para expresiones), o modifica el `Entorno` (para instrucciones).

Esto corresponde a un **intérprete de árbol (tree-walking interpreter)**
que combina el análisis semántico y la ejecución, apropiado para un
intérprete (no un compilador que genere código de bajo nivel).

###  Representación de valores

`ResultadoObtenido(valor, tipo)` es el "valor tipado" que viaja por todo el
árbol. El tipo `"None"` se usa como **valor centinela de error**: cuando una
operación no es válida semánticamente, se registra el error en el entorno
y se devuelve `ResultadoObtenido(None, "None")` (o `"None"`), lo que permite
que el resto del árbol detecte la propagación del error y detenga solo esa
rama de evaluación, sin abortar el programa completo.

###  Tabla de tipos y promoción (implementadas en `OperacionBinaria`)

- `i32 + i32 → i32`, `i32/f64 mezcla → f64` (promoción automática si
  cualquiera de los operandos es `f64`).
- `String + String → String` (concatenación).
- `String * i32` / `i32 * String → String` (repetición de cadena).
- Comparaciones (`== != > < >= <=`): válidas entre numéricos, entre
  `bool`/`bool` (solo `==`/`!=`), entre `String`/`String`, entre
  `char`/`char`, y entre `i32`/`char` (comparando código Unicode).
- `&&` / `||` implementan **cortocircuito**: si el operando izquierdo ya
  determina el resultado (`false` en `&&`, `true` en `||`), el operando
  derecho no se evalúa.
- División y módulo entre cero se detectan y reportan como error semántico
  antes de causar una excepción de Python.

###  Ámbitos y tabla de símbolos (`tabla_simbolos.py`)

`Entorno` implementa una lista enlazada de ámbitos (`anterior`), cada uno
con su propia tabla `dict` (`identificador → Simbolo`):

- `obtener_variable` busca en el ámbito actual y sube recursivamente por
  `anterior` (resolución léxica clásica).
- `actualizar_variable` solo modifica el valor si `simbolo.es_mutable` es
  `True`; en caso contrario devuelve `"ERROR_INMUTABLE"`, que
  `AsignacionVariable.ejecutar` traduce en un error semántico.
- Cada `Bloque.ejecutar` crea un nuevo `Entorno(anterior=entorno,
  nombre_ambito="Bloque")`, delimitando el alcance de las variables
  declaradas dentro de `{ ... }` (if/else, while, loop, cuerpos de función).
- `todos_los_simbolos` es una lista **compartida entre todos los ámbitos**
  (se propaga desde el entorno global vía `anterior.todos_los_simbolos`),
  usada para construir el reporte final de la tabla de símbolos con todos
  los identificadores vistos durante la ejecución, sin importar su ámbito.

###  Control de flujo con excepciones de Python

`break`, `continue` y `return` se implementan lanzando excepciones propias
(`BreakException`, `ContinueException`, `ReturnException`), capturadas en
los nodos `CicloWhile`, `CicloLoop` y `LlamadaFuncion` respectivamente. Las
excepciones llevan la etiqueta (`etiqueta`) para soportar `break 'outer;` /
`continue 'outer;` en bucles anidados: si la etiqueta de la excepción no
coincide con la del bucle actual, se vuelve a lanzar (`raise`) para que el
bucle exterior correspondiente la capture.

###  Funciones (`DeclaracionFuncion` / `LlamadaFuncion`)

- Declarar una función registra un `Simbolo` de categoría `"Funcion"` cuyo
  `valor` es el propio nodo `DeclaracionFuncion` (para poder acceder a sus
  parámetros, tipo de retorno y bloque en el momento de la llamada).
- Al llamar la función se crea un nuevo `Entorno` hijo (`Funcion_<nombre>`),
  se valida el número de argumentos y el tipo de cada uno contra los
  parámetros declarados, y se ejecuta el bloque; un `return` se captura
  como `ReturnException` y se valida contra el tipo de retorno declarado.
- `typeof(x)` y `random(min, max)` están implementadas como funciones
  embebidas especiales dentro de `LlamadaFuncion.ejecutar`.

###  Arreglos, slices y structs

- `ArregloLiteral` valida que todos los elementos tengan el mismo tipo.
- `AccesoArreglo` valida que el índice sea `i32` y controla `IndexError`
  para reportar "Índice fuera de rango" en vez de detener el programa.
- `SliceArreglo` (`&arr[a..b]`) devuelve una sublista de Python.
- `DeclaracionStruct` guarda la definición de campos; `InstanciacionStruct`
  construye un `dict` de `ResultadoObtenido` por campo; `AccesoAtributo` /
  `AsignacionAtributo` leen/escriben esos campos.

### 5.7 Métodos embebidos de `String` y arreglos (`LlamadaMetodoString`)

`String`: `.len()` (vía `MetodoLen`), `.replace()`, `.contains()`,
`.to_uppercase()`, `.to_lowercase()`, `.split()`, `.split_whitespace()`.
Arreglos: `.len()`, `.contains()`, `.reverse()` (in-place), `.collect()`.

## 6. Generación de reportes

- **Errores** (`app.py`): se concatenan `errores_lexicos + errores_sintacticos
  + entorno_global.errores` y se devuelven como JSON; el front-end los
  renderiza en la pestaña **Errores**.
- **Tabla de símbolos**: `generar_reporte_simbolos_html()` construye un
  archivo `reporte_simbolos.html` autónomo (con estilos embebidos), además
  de devolver la lista `simbolos` en el JSON para pintar la tabla en la
  pestaña correspondiente de la SPA.
- **AST**: `generar_dot_ast(ast)` recorre recursivamente cada nodo por
  reflexión (`vars(nodo)`), etiquetando cada caja con el nombre de la clase
  y, si existe, el atributo `id`, `operador` o `valor` del nodo. El DOT
  resultante se guarda en `reporte_ast.dot` y se compila con el binario
  `dot` de Graphviz (`subprocess.run`) a `.png`, `.pdf` y `.svg`; el SVG se
  incrusta directamente en la pestaña **AST** de la interfaz.

## 7. Interfaz web (`templates/index.html`)

SPA de una sola página (Bootstrap 5 + JavaScript vanilla) con:

- Editor de texto con numeración de líneas sincronizada (`actualizarLineas`,
  `sincronizarScroll`).
- Botones **Nuevo**, **Abrir** (input `file` oculto), **Guardar** (descarga
  el contenido del editor como archivo) y **Ejecutar**.
- `ejecutarCodigo()` hace `fetch('/ejecutar', { method:'POST', body:
  JSON.stringify({ codigo }) })` y vuelca la respuesta en la consola y en
  las tres pestañas (Errores / Tabla de símbolos / AST) mediante pestañas
  Bootstrap (`nav-tabs`).

## 8. Decisiones de diseño

- **Intérprete de árbol de una sola pasada**: se combinó el análisis
  semántico con la ejecución (en vez de separarlos en fases independientes)
  porque el objetivo del proyecto es interpretar OxigenScript directamente,
  no generar código de bajo nivel; esto simplifica la arquitectura y evita
  recorrer el AST dos veces.
- **Valor centinela `"None"`** en vez de excepciones Python para errores
  semánticos: permite que la ejecución continúe evaluando el resto del
  programa (resiliencia), en línea con el requisito de reportar múltiples
  errores en una sola ejecución.
- **Ejecución automática de `main()`**: en vez de exigir que el usuario
  llame explícitamente a `main()`, el backend ejecuta primero todas las
  instrucciones de nivel superior (que registran funciones/variables
  globales) y luego invoca `main` automáticamente si existe, replicando el
  comportamiento de un programa Rust real.
- **Ámbitos como lista enlazada (`Entorno.anterior`)**: modelo simple y
  suficiente para resolución léxica de identificadores, sin necesidad de
  una pila explícita.

## 9. Desafíos enfrentados

- **Ambigüedad `if cond { }` vs. `Struct { }`**: se resolvió separando la
  gramática en `expresion` (permite instanciación de struct) y
  `expresion_sin_struct` (la usan las condiciones de `if`/`while`/`match`).
- **Etiquetas de loop vs. caracteres**: en el lexer, `CARACTER` (`'x'`) y
  `ETIQUETA` (`'nombre`) podían confundirse; se resolvió con expresiones
  regulares distintas y el orden de las funciones de PLY (que determina
  la prioridad de coincidencia).
- **Recuperación de errores sin duplicar reportes**: al propagar el tipo
  `"None"` en cascada por el árbol, se evita que un mismo error semántico se
  reporte múltiples veces en operaciones compuestas (p. ej. `a + b + c`
  cuando `b` ya es inválido).
- **Captura de la salida del programa**: dado que `Imprimir` usa `print()`
  de Python, fue necesario redirigir `sys.stdout` a un buffer por cada
  petición HTTP y restaurarlo en el bloque `finally`, para no mezclar la
  salida de distintas ejecuciones concurrentes ni los logs del servidor.

## 10. Limitaciones conocidas

- El sistema de tipos se valida en tiempo de ejecución (no hay una fase de
  chequeo de tipos independiente antes de interpretar).
- `match` solo soporta patrones literales y el comodín `_`; no soporta
  rangos ni patrones sobre structs.
- La columna reportada en los errores corresponde a la posición absoluta en
  el buffer de texto (`lexpos`), no a la columna dentro de la línea.
- No se implementa un *borrow checker* real de Rust: los slices (`&arr[a..b]`)
  devuelven una copia de la porción del arreglo.
