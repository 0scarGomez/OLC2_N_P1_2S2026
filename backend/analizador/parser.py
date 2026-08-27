import ply.yacc as yacc

from backend.analizador.lexer import tokens, errores_lexicos
from backend.analizador.ast_nodes import (
    DeclaracionVariable, Primitivo, OperacionBinaria, 
    Imprimir, AccesoVariable, Bloque, SentenciaIf,
    AsignacionVariable, CicloWhile, SentenciaBreak, SentenciaContinue
)

errores_sintacticos = []

# Definir precedencia 
precedence = (
    ('left', 'OR'),
    ('left', 'AND'),
    ('left', 'IGUAL_IGUAL', 'DIFERENTE', 'MAYOR_QUE', 'MENOR_QUE', 'MAYOR_IGUAL', 'MENOR_IGUAL'),
    ('left', 'MAS', 'MENOS'),
    ('left', 'POR', 'DIV', 'MOD'),
    ('right', 'NOT'), # Negación unaria
)

# Regla inicial
def p_programa(p):
    '''programa : instrucciones'''
    p[0] = p[1]

def p_instrucciones_lista(p):
    '''instrucciones : instrucciones instruccion
                     | instruccion'''
    if len(p) == 3:
        p[0] = p[1] + [p[2]]
    else:
        p[0] = [p[1]]

# Instrucción: Declaración de variables
def p_instruccion_declaracion(p):
    '''instruccion : R_LET R_MUT ID DOS_PUNTOS tipo IGUAL expresion PUNTO_COMA
                   | R_LET ID DOS_PUNTOS tipo IGUAL expresion PUNTO_COMA'''
    if p[2] == 'mut':
        p[0] = DeclaracionVariable(True, p[3], p[5], p[7], p.lineno(1), p.lexpos(1))
    else:
        p[0] = DeclaracionVariable(False, p[2], p[4], p[6], p.lineno(1), p.lexpos(1))

def p_instruccion_println(p):
    '''instruccion : R_PRINTLN NOT PAR_IZQ expresion PAR_DER PUNTO_COMA'''
    p[0] = Imprimir(p[4], p.lineno(1), p.lexpos(1))

# Tipos de datos
def p_tipo(p):
    '''tipo : R_I32 
            | R_F64 
            | R_STRING 
            | R_BOOL'''
    p[0] = p[1]

# Expresiones binarias
def p_expresion_binaria(p):
    '''expresion : expresion MAS expresion
                 | expresion MENOS expresion
                 | expresion POR expresion
                 | expresion DIV expresion
                 | expresion MOD expresion
                 | expresion MAYOR_QUE expresion
                 | expresion MENOR_QUE expresion
                 | expresion MAYOR_IGUAL expresion
                 | expresion MENOR_IGUAL expresion
                 | expresion IGUAL_IGUAL expresion
                 | expresion DIFERENTE expresion
                 | expresion AND expresion
                 | expresion OR expresion'''
    p[0] = OperacionBinaria(p[2], p[1], p[3], p.lineno(2), p.lexpos(2))

# Valores primitivos
def p_expresion_primitiva(p):
    '''expresion : ENTERO
                 | DECIMAL
                 | CADENA
                 | R_TRUE
                 | R_FALSE'''
    if isinstance(p[1], int):
        tipo = 'i32'
        valor = p[1]
    elif isinstance(p[1], float):
        tipo = 'f64'
        valor = p[1]
    elif p[1] == 'true':
        tipo = 'bool'
        valor = True
    elif p[1] == 'false':
        tipo = 'bool'
        valor = False
    else:
        tipo = 'String'
        valor = p[1]
    
    p[0] = Primitivo(valor, tipo, p.lineno(1), p.lexpos(1))

def p_expresion_id(p):
    '''expresion : ID'''
    p[0] = AccesoVariable(p[1], p.lineno(1), p.lexpos(1))

# Manejo de Errores Sintácticos
def p_error(p):
    if p:
        mensaje = f"Se esperaba un token válido, pero se encontró '{p.value}'"
        print(f"[Error Sintáctico] Línea {p.lineno}\n{mensaje}")
        errores_sintacticos.append({
            "tipo": "Sintáctico",
            "descripcion": mensaje,
            "linea": p.lineno
        })
    else:
        print("[Error Sintáctico] Fin de archivo inesperado.")
        
def p_bloque(p):
    '''bloque : LLAVE_IZQ instrucciones LLAVE_DER
              | LLAVE_IZQ LLAVE_DER'''
    if len(p) == 4:
        p[0] = Bloque(p[2], p.lineno(1), p.lexpos(1))
    else:
        p[0] = Bloque([], p.lineno(1), p.lexpos(1))

# 3. Agregar la regla de Sentencia IF / ELSE
def p_instruccion_if(p):
    '''instruccion : R_IF expresion bloque
                   | R_IF expresion bloque R_ELSE bloque'''
    if len(p) == 4:
        p[0] = SentenciaIf(p[2], p[3], None, p.lineno(1), p.lexpos(1))
    else:
        p[0] = SentenciaIf(p[2], p[3], p[5], p.lineno(1), p.lexpos(1))

# regla asignacion de variable
def p_instruccion_asignacion(p):
    '''instruccion : ID IGUAL expresion PUNTO_COMA'''
    p[0] = AsignacionVariable(p[1], p[3], p.lineno(1), p.lexpos(1))

# regla del ciclo while
def p_instruccion_while(p):
    '''instruccion : R_WHILE expresion bloque'''
    p[0] = CicloWhile(p[2], p[3], p.lineno(1), p.lexpos(1))
parser = yacc.yacc()

def p_instruccion_break(p):
    '''instruccion : R_BREAK PUNTO_COMA'''
    p[0] = SentenciaBreak(p.lineno(1), p.lexpos(1))

def p_instruccion_continue(p):
    '''instruccion : R_CONTINUE PUNTO_COMA'''
    p[0] = SentenciaContinue(p.lineno(1), p.lexpos(1))
    
parser = yacc.yacc(write_tables=False, debug=False)