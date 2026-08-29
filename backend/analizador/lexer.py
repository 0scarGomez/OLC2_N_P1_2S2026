import ply.lex as lex

# Lista de Errores léxicos 
errores_lexicos = []

# Palabras Reservadas
reservadas = {
    'fn': 'R_FN',
    'let': 'R_LET',
    'mut': 'R_MUT',
    'if': 'R_IF',
    'else': 'R_ELSE',
    'while': 'R_WHILE',
    'loop': 'R_LOOP',
    'match': 'R_MATCH',
    'break': 'R_BREAK',
    'continue': 'R_CONTINUE',
    'return': 'R_RETURN',
    'struct': 'R_STRUCT',
    'true': 'R_TRUE',
    'false': 'R_FALSE',
    'i32': 'R_I32',
    'f64': 'R_F64',
    'bool': 'R_BOOL',
    'char': 'R_CHAR',
    'String': 'R_STRING',
    'println': 'R_PRINTLN',
}

# Lista de Tokens
tokens = [
    'ID', 'ENTERO', 'DECIMAL', 'CADENA', 'CARACTER',
    
    # Operadores Aritméticos
    'MAS', 'MENOS', 'POR', 'DIV', 'MOD',
    
    # Operadores Relacionales
    'IGUAL_IGUAL', 'DIFERENTE', 'MAYOR_QUE', 'MENOR_QUE', 'MAYOR_IGUAL', 'MENOR_IGUAL',
    
    # Operadores Lógicos
    'NOT', 'AND', 'OR',
    
    # Operadores de Asignación
    'IGUAL', 'MAS_IGUAL', 'MENOS_IGUAL', 'POR_IGUAL', 'DIV_IGUAL', 'MOD_IGUAL',
    
    # Símbolos de Agrupación y Puntuación
    'PAR_IZQ', 'PAR_DER', 'LLAVE_IZQ', 'LLAVE_DER', 'COR_IZQ', 'COR_DER',
    'PUNTO_COMA', 'DOS_PUNTOS', 'COMA', 'PUNTO', 'FLECHA', 'FLECHA_DOBLE', 'AMPERSAND',
    'CUATRO_PUNTOS', 'ETIQUETA', 'PUNTO_PUNTO',
] + list(reservadas.values())

# Expresiones Regulares para Tokens Simples
t_MAS_IGUAL   = r'\+='
t_MENOS_IGUAL = r'-='
t_POR_IGUAL   = r'\*='
t_DIV_IGUAL   = r'/='
t_MOD_IGUAL   = r'%='
t_IGUAL_IGUAL = r'=='
t_DIFERENTE   = r'!='
t_MAYOR_IGUAL = r'>='
t_MENOR_IGUAL = r'<='
t_FLECHA      = r'->'
t_FLECHA_DOBLE= r'=>'
t_AND         = r'&&'
t_OR          = r'\|\|'

t_MAS       = r'\+'
t_MENOS     = r'-'
t_POR       = r'\*'
t_DIV       = r'/'
t_MOD       = r'%'
t_IGUAL     = r'='
t_MAYOR_QUE = r'>'
t_MENOR_QUE = r'<'
t_NOT       = r'!'
t_PAR_IZQ   = r'\('
t_PAR_DER   = r'\)'
t_LLAVE_IZQ = r'\{'
t_LLAVE_DER = r'\}'
t_COR_IZQ   = r'\['
t_COR_DER   = r'\]'
t_PUNTO_COMA= r';'
t_DOS_PUNTOS= r':'
t_COMA      = r','
t_PUNTO_PUNTO = r'\.\.'
t_PUNTO     = r'\.'
t_AMPERSAND = r'&'
t_CUATRO_PUNTOS = r'::'

# Expresiones Regulares con Funciones
def t_DECIMAL(t):
    r'\d+\.\d+'
    t.value = float(t.value)
    return t

def t_ENTERO(t):
    r'\d+'
    t.value = int(t.value)
    return t

def t_RAW_STRING_HASH(t):
    r'r\#"[\s\S]*?"\#'
    # Quita r#" al inicio (3 chars) y "# al final (2 chars)
    t.value = t.value[3:-2]
    t.type = 'CADENA'
    return t

def t_RAW_STRING(t):
    r'r"[\s\S]*?"'
    # Quita r" al inicio (2 chars) y " al final (1 char)
    t.value = t.value[2:-1]
    t.type = 'CADENA'
    return t

def t_CADENA(t):
    r'\"([^\\\n]|(\\.))*?\"'
    # Quita las comillas inicial y final
    val = t.value[1:-1]
    # Procesa los saltos de línea y escapes nativos de la cadena normal
    t.value = val.encode('utf-8').decode('unicode_escape')
    return t

def t_CARACTER(t):
    r'\'[^\']\''
    t.value = t.value[1:-1]
    return t

def t_ID(t):
    r'[a-zA-Z_][a-zA-Z_0-9]*'
    t.type = reservadas.get(t.value, 'ID')
    return t

# Comentario de Línea
def t_COMENTARIO_LINEA(t):
    r'//.*'
    pass

# Comentario de Bloque (Soporta cerrados y no cerrados)
def t_COMENTARIO_MULTILINEA(t):
    r'/\*[\s\S]*?\*/|/\*[\s\S]*'
    if not t.value.endswith('*/'):
        line_start = t.lexer.lexdata.rfind('\n', 0, t.lexer.lexpos) + 1
        columna = (t.lexer.lexpos - line_start) + 1
        mensaje_error = "Comentario de bloque no cerrado (se esperaba '*/')"
        print(f"[Error Léxico] Línea {t.lexer.lineno}, Columna {columna}\n{mensaje_error}")
        errores_lexicos.append({
            "tipo": "Léxico",
            "descripcion": mensaje_error,
            "linea": t.lexer.lineno,
            "columna": columna
        })
    t.lexer.lineno += t.value.count('\n')

t_ignore = ' \t'

def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)

def t_ETIQUETA(t):
    r'\'[a-zA-Z_][a-zA-Z_0-9]*'
    return t

def t_error(t):
    line_start = t.lexer.lexdata.rfind('\n', 0, t.lexer.lexpos) + 1
    columna = (t.lexer.lexpos - line_start) + 1
    
    mensaje_error = f"Carácter no reconocido: '{t.value[0]}'"
    print(f"[Error Léxico] Línea {t.lexer.lineno}, Columna {columna}\n{mensaje_error}")
    
    errores_lexicos.append({
        "tipo": "Léxico",
        "descripcion": mensaje_error,
        "linea": t.lexer.lineno,
        "columna": columna
    })
    
    t.lexer.skip(1)

lexer = lex.lex()