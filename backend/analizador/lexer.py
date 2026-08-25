import ply.lex as lex

# Lista de Errores lexicos 
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
    'println': 'R_PRINTLN', # Se manejara junto con el '!' en el parser o como token especial
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
    'PUNTO_COMA', 'DOS_PUNTOS', 'COMA', 'PUNTO', 'FLECHA', 'FLECHA_DOBLE', 'AMPERSAND'
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
t_PUNTO     = r'\.'
t_AMPERSAND = r'&'

# Expresiones Regulares con Funciones

# Decimales (f64)
def t_DECIMAL(t):
    r'\d+\.\d+'
    t.value = float(t.value)
    return t

# Enteros (i32)
def t_ENTERO(t):
    r'\d+'
    t.value = int(t.value)
    return t

# Cadenas 
def t_CADENA(t):
    r'\"([^\\\n]|(\\.))*?\"'
    t.value = str(t.value)
    return t

# Identificadores y Palabras Reservadas
def t_ID(t):
    r'[a-zA-Z_][a-zA-Z_0-9]*'
    # Verifica si el ID es una palabra reservada
    t.type = reservadas.get(t.value, 'ID')
    return t

# Manejo de Comentarios
# Comentario de una linea 
def t_COMENTARIO_LINEA(t):
    r'//.*'
    pass

# Comentario multilinea 
def t_COMENTARIO_MULTILINEA(t):
    r'/\*(.|\n)*?\*/'
    t.lexer.lineno += t.value.count('\n')
    pass

# Reglas para ignorar caracteres 
t_ignore = ' \t'

# Cuenta saltos de linea para saber en que linea estamos
def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)

# Manejo de Errores lexicos
def t_error(t):
    # Calculamos la columna
    line_start = t.lexer.lexdata.rfind('\n', 0, t.lexer.lexpos) + 1
    columna = (t.lexer.lexpos - line_start) + 1
    
    mensaje_error = f"Carácter no reconocido: '{t.value[0]}'"
    print(f"[Error Léxico] Línea {t.lexer.lineno}, Columna {columna}\n{mensaje_error}")
    
    # Guardamos el error para el reporte final
    errores_lexicos.append({
        "tipo": "Léxico",
        "descripcion": mensaje_error,
        "linea": t.lexer.lineno,
        "columna": columna
    })
    
    t.lexer.skip(1) # Resiliencia: se salta el caracter y continua

lexer = lex.lex()