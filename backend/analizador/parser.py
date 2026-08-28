import ply.yacc as yacc
from backend.analizador.lexer import tokens
from backend.analizador.ast_nodes import (
    DeclaracionVariable, Primitivo, OperacionBinaria, 
    Imprimir, AccesoVariable, Bloque, SentenciaIf,
    AsignacionVariable, CicloWhile, SentenciaBreak, SentenciaContinue,
    DeclaracionFuncion, LlamadaFuncion, SentenciaReturn,
    ArregloLiteral, AccesoArreglo, AsignacionArreglo,
    DeclaracionStruct, InstanciacionStruct, AccesoAtributo,
    AsignacionAtributo, MetodoLen, CasoMatch, SentenciaMatch
)

# Precedencia de operadores
precedence = (
    ('left', 'OR'),
    ('left', 'AND'),
    ('left', 'IGUAL_IGUAL', 'DIFERENTE'),
    ('left', 'MAYOR_QUE', 'MENOR_QUE', 'MAYOR_IGUAL', 'MENOR_IGUAL'),
    ('left', 'MAS', 'MENOS'),
    ('left', 'POR', 'DIV', 'MOD'),
)

def p_init(p):
    '''init : instrucciones'''
    p[0] = p[1]

def p_instrucciones(p):
    '''instrucciones : instrucciones instruccion
                    | instruccion'''
    if len(p) == 3:
        p[0] = p[1] + [p[2]]
    else:
        p[0] = [p[1]]

def p_instruccion(p):
    '''instruccion : instruccion_declaracion
                   | instruccion_asignacion
                   | instruccion_imprimir
                   | instruccion_if
                   | instruccion_while
                   | instruccion_break
                   | instruccion_continue
                   | instruccion_funcion
                   | instruccion_return
                   | instruccion_struct
                   | instruccion_asignacion_arreglo
                   | instruccion_asignacion_atributo
                   | instruccion_match'''
    p[0] = p[1]

def p_instruccion_declaracion(p):
    '''instruccion_declaracion : R_LET R_MUT ID DOS_PUNTOS tipo IGUAL expresion PUNTO_COMA
                               | R_LET ID DOS_PUNTOS tipo IGUAL expresion PUNTO_COMA'''
    if len(p) == 9:
        # Orden de tu AST: mutabilidad, ID, tipo, expresion, linea, columna
        p[0] = DeclaracionVariable(True, p[3], p[5], p[7], p.lineno(1), p.lexpos(1))
    else:
        # Orden de tu AST: mutabilidad, ID, tipo, expresion, linea, columna
        p[0] = DeclaracionVariable(False, p[2], p[4], p[6], p.lineno(1), p.lexpos(1))

def p_instruccion_asignacion(p):
    '''instruccion_asignacion : ID IGUAL expresion PUNTO_COMA'''
    p[0] = AsignacionVariable(p[1], p[3], p.lineno(1), p.lexpos(1))

# Regla dinámica para soportar 'println!' tanto con '!' junto como separado
def p_instruccion_imprimir(p):
    exp = p[3] if len(p) == 6 else p[4]
    p[0] = Imprimir(exp, p.lineno(1), p.lexpos(1))

_reglas_imprimir = ["R_PRINTLN PAR_IZQ expresion PAR_DER PUNTO_COMA"]
for _tok in ['ADMIRACION', 'NOT', 'EXCLAMACION']:
    if _tok in tokens:
        _reglas_imprimir.append(f"R_PRINTLN {_tok} PAR_IZQ expresion PAR_DER PUNTO_COMA")

p_instruccion_imprimir.__doc__ = "instruccion_imprimir : " + "\n| ".join(_reglas_imprimir)

def p_instruccion_if(p):
    '''instruccion_if : R_IF expresion_sin_struct bloque R_ELSE bloque
                     | R_IF expresion_sin_struct bloque'''
    if len(p) == 6:
        p[0] = SentenciaIf(p[2], p[3], p[5], p.lineno(1), p.lexpos(1))
    else:
        p[0] = SentenciaIf(p[2], p[3], None, p.lineno(1), p.lexpos(1))

def p_instruccion_while(p):
    '''instruccion_while : R_WHILE expresion_sin_struct bloque'''
    p[0] = CicloWhile(p[2], p[3], p.lineno(1), p.lexpos(1))

def p_instruccion_break(p):
    '''instruccion_break : R_BREAK PUNTO_COMA'''
    p[0] = SentenciaBreak(p.lineno(1), p.lexpos(1))

def p_instruccion_continue(p):
    '''instruccion_continue : R_CONTINUE PUNTO_COMA'''
    p[0] = SentenciaContinue(p.lineno(1), p.lexpos(1))

def p_instruccion_funcion(p):
    '''instruccion_funcion : R_FN ID PAR_IZQ parametros PAR_DER FLECHA tipo bloque
                           | R_FN ID PAR_IZQ PAR_DER FLECHA tipo bloque
                           | R_FN ID PAR_IZQ parametros PAR_DER bloque
                           | R_FN ID PAR_IZQ PAR_DER bloque'''
    if len(p) == 9:
        p[0] = DeclaracionFuncion(p[2], p[4], p[7], p[8], p.lineno(1), p.lexpos(1))
    elif len(p) == 8:
        p[0] = DeclaracionFuncion(p[2], [], p[6], p[7], p.lineno(1), p.lexpos(1))
    elif len(p) == 7:
        p[0] = DeclaracionFuncion(p[2], p[4], None, p[6], p.lineno(1), p.lexpos(1))
    elif len(p) == 6:
        p[0] = DeclaracionFuncion(p[2], [], None, p[5], p.lineno(1), p.lexpos(1))

def p_parametros(p):
    '''parametros : parametros COMA parametro
                  | parametro'''
    if len(p) == 4:
        p[0] = p[1] + [p[3]]
    else:
        p[0] = [p[1]]

def p_parametro(p):
    '''parametro : ID DOS_PUNTOS tipo'''
    p[0] = (p[1], p[3])

def p_instruccion_return(p):
    '''instruccion_return : R_RETURN expresion PUNTO_COMA
                          | R_RETURN PUNTO_COMA'''
    exp = p[2] if len(p) == 4 else None
    p[0] = SentenciaReturn(exp, p.lineno(1), p.lexpos(1))

def p_instruccion_struct(p):
    '''instruccion_struct : R_STRUCT ID LLAVE_IZQ campos_struct LLAVE_DER'''
    p[0] = DeclaracionStruct(p[2], dict(p[4]), p.lineno(1), p.lexpos(1))

def p_campos_struct(p):
    '''campos_struct : campos_struct COMA campo_struct
                    | campo_struct'''
    if len(p) == 4:
        p[0] = p[1] + [p[3]]
    else:
        p[0] = [p[1]]

def p_campo_struct(p):
    '''campo_struct : ID DOS_PUNTOS tipo'''
    p[0] = (p[1], p[3])

def p_instruccion_asignacion_arreglo(p):
    '''instruccion_asignacion_arreglo : ID COR_IZQ expresion COR_DER IGUAL expresion PUNTO_COMA'''
    p[0] = AsignacionArreglo(p[1], p[3], p[6], p.lineno(1), p.lexpos(1))

def p_instruccion_asignacion_atributo(p):
    '''instruccion_asignacion_atributo : ID PUNTO ID IGUAL expresion PUNTO_COMA'''
    p[0] = AsignacionAtributo(p[1], p[3], p[5], p.lineno(1), p.lexpos(1))

def p_instruccion_match(p):
    '''instruccion_match : R_MATCH expresion_sin_struct LLAVE_IZQ casos_match LLAVE_DER'''
    p[0] = SentenciaMatch(p[2], p[4], p.lineno(1), p.lexpos(1))

def p_casos_match(p):
    '''casos_match : casos_match_lista'''
    p[0] = p[1]

def p_casos_match_lista(p):
    '''casos_match_lista : casos_match_lista caso_match_item
                        | caso_match_item'''
    if len(p) == 3:
        p[0] = p[1] + [p[2]]
    else:
        p[0] = [p[1]]

def p_caso_match_item(p):
    '''caso_match_item : caso_match COMA
                       | caso_match'''
    p[0] = p[1]

def p_caso_match(p):
    '''caso_match : expresion FLECHA_DOBLE bloque'''
    p[0] = CasoMatch(p[1], p[3])

def p_bloque(p):
    '''bloque : LLAVE_IZQ instrucciones LLAVE_DER
              | LLAVE_IZQ LLAVE_DER'''
    if len(p) == 4:
        p[0] = Bloque(p[2], p.lineno(1), p.lexpos(1))
    else:
        p[0] = Bloque([], p.lineno(1), p.lexpos(1))

def p_tipo(p):
    '''tipo : R_I32
            | R_F64
            | R_BOOL
            | R_STRING
            | COR_IZQ tipo COR_DER
            | ID'''
    if len(p) == 4:
        p[0] = f"[{p[2]}]"
    else:
        p[0] = p[1]

def p_expresion(p):
    '''expresion : expresion_sin_struct
                 | ID LLAVE_IZQ valores_campos LLAVE_DER'''
    if len(p) == 2:
        p[0] = p[1]
    else:
        p[0] = InstanciacionStruct(p[1], dict(p[3]), p.lineno(1), p.lexpos(1))

def p_valores_campos(p):
    '''valores_campos : valores_campos COMA valor_campo
                      | valor_campo'''
    if len(p) == 4:
        p[0] = p[1] + [p[3]]
    else:
        p[0] = [p[1]]

def p_valor_campo(p):
    '''valor_campo : ID DOS_PUNTOS expresion'''
    p[0] = (p[1], p[3])

def p_expresion_primitiva(p):
    '''expresion_sin_struct : ENTERO
                            | DECIMAL
                            | CADENA
                            | R_TRUE
                            | R_FALSE'''
    if isinstance(p[1], int): tipo, valor = 'i32', p[1]
    elif isinstance(p[1], float): tipo, valor = 'f64', p[1]
    elif p[1] == 'true': tipo, valor = 'bool', True
    elif p[1] == 'false': tipo, valor = 'bool', False
    else: tipo, valor = 'String', p[1]
    p[0] = Primitivo(valor, tipo, p.lineno(1), p.lexpos(1))

def p_expresion_id(p):
    '''expresion_sin_struct : ID'''
    p[0] = AccesoVariable(p[1], p.lineno(1), p.lexpos(1))

def p_expresion_binaria(p):
    '''expresion_sin_struct : expresion_sin_struct MAS expresion_sin_struct
                             | expresion_sin_struct MENOS expresion_sin_struct
                             | expresion_sin_struct POR expresion_sin_struct
                             | expresion_sin_struct DIV expresion_sin_struct
                             | expresion_sin_struct MOD expresion_sin_struct
                             | expresion_sin_struct MAYOR_QUE expresion_sin_struct
                             | expresion_sin_struct MENOR_QUE expresion_sin_struct
                             | expresion_sin_struct MAYOR_IGUAL expresion_sin_struct
                             | expresion_sin_struct MENOR_IGUAL expresion_sin_struct
                             | expresion_sin_struct IGUAL_IGUAL expresion_sin_struct
                             | expresion_sin_struct DIFERENTE expresion_sin_struct
                             | expresion_sin_struct AND expresion_sin_struct
                             | expresion_sin_struct OR expresion_sin_struct'''
    p[0] = OperacionBinaria(p[2], p[1], p[3], p.lineno(2), p.lexpos(2))

def p_expresion_acceso_arreglo(p):
    '''expresion_sin_struct : expresion_sin_struct COR_IZQ expresion COR_DER'''
    p[0] = AccesoArreglo(p[1], p[3], p.lineno(2), p.lexpos(2))

def p_expresion_acceso_atributo(p):
    '''expresion_sin_struct : expresion_sin_struct PUNTO ID'''
    p[0] = AccesoAtributo(p[1], p[3], p.lineno(2), p.lexpos(2))

def p_expresion_metodo_len(p):
    '''expresion_sin_struct : expresion_sin_struct PUNTO ID PAR_IZQ PAR_DER'''
    if p[3] == 'len':
        p[0] = MetodoLen(p[1], p.lineno(2), p.lexpos(2))

def p_expresion_llamada(p):
    '''expresion_sin_struct : ID PAR_IZQ argumentos PAR_DER
                             | ID PAR_IZQ PAR_DER'''
    args = p[3] if len(p) == 5 else []
    p[0] = LlamadaFuncion(p[1], args, p.lineno(1), p.lexpos(1))

def p_argumentos(p):
    '''argumentos : argumentos COMA expresion
                  | expresion'''
    if len(p) == 4:
        p[0] = p[1] + [p[3]]
    else:
        p[0] = [p[1]]

def p_expresion_arreglo_literal(p):
    '''expresion_sin_struct : COR_IZQ elementos COR_DER
                             | COR_IZQ COR_DER'''
    if len(p) == 4:
        p[0] = ArregloLiteral(p[2], p.lineno(1), p.lexpos(1))
    else:
        p[0] = ArregloLiteral([], p.lineno(1), p.lexpos(1))

def p_elementos(p):
    '''elementos : elementos COMA expresion
                  | expresion'''
    if len(p) == 4:
        p[0] = p[1] + [p[3]]
    else:
        p[0] = [p[1]]

def p_error(p):
    if p:
        print(f"[Error Sintáctico] Línea {p.lineno}\nSe esperaba un token válido, pero se encontró '{p.value}'")
    else:
        print("[Error Sintáctico] Fin de archivo inesperado")

parser = yacc.yacc(write_tables=False, debug=False)