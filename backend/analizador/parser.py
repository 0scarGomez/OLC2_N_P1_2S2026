import ply.yacc as yacc
from backend.analizador.lexer import tokens
from backend.analizador.ast_nodes import (
    DeclaracionVariable, Primitivo, OperacionBinaria, OperacionUnaria, 
    Imprimir, AccesoVariable, Bloque, SentenciaIf,
    AsignacionVariable, CicloWhile, SentenciaBreak, SentenciaContinue,
    DeclaracionFuncion, LlamadaFuncion, SentenciaReturn,
    ArregloLiteral, AccesoArreglo, AsignacionArreglo,
    DeclaracionStruct, InstanciacionStruct, AccesoAtributo,
    AsignacionAtributo, MetodoLen, CasoMatch, SentenciaMatch, CicloLoop, 
    ArregloRepeticion, SliceArreglo, CrearStringNuevo, LlamadaMetodoString
)

errores_sintacticos = []

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
                   | instruccion_match
                   | instruccion_loop
                   | bloque'''
    p[0] = p[1]

def p_instruccion_declaracion(p):
    '''instruccion_declaracion : R_LET R_MUT ID DOS_PUNTOS tipo IGUAL expresion PUNTO_COMA
                               | R_LET ID DOS_PUNTOS tipo IGUAL expresion PUNTO_COMA
                               | R_LET R_MUT ID IGUAL expresion PUNTO_COMA
                               | R_LET ID IGUAL expresion PUNTO_COMA
                               | R_LET R_MUT ID DOS_PUNTOS tipo PUNTO_COMA
                               | R_LET ID DOS_PUNTOS tipo PUNTO_COMA'''
    if len(p) == 9:
        p[0] = DeclaracionVariable(True, p[3], p[5], p[7], p.lineno(1), p.lexpos(1))
    elif len(p) == 8:
        p[0] = DeclaracionVariable(False, p[2], p[4], p[6], p.lineno(1), p.lexpos(1))
    elif len(p) == 7:
        if p[4] == '=':
            p[0] = DeclaracionVariable(True, p[3], None, p[5], p.lineno(1), p.lexpos(1))
        else:
            p[0] = DeclaracionVariable(True, p[3], p[5], None, p.lineno(1), p.lexpos(1))
    elif len(p) == 6:
        if p[3] == '=':
            p[0] = DeclaracionVariable(False, p[2], None, p[4], p.lineno(1), p.lexpos(1))
        else:
            p[0] = DeclaracionVariable(False, p[2], p[4], None, p.lineno(1), p.lexpos(1))

def p_instruccion_loop(p):
    '''instruccion_loop : R_LOOP bloque
                        | ETIQUETA DOS_PUNTOS R_LOOP bloque'''
    if len(p) == 3:
        p[0] = CicloLoop(p[2], None, p.lineno(1), p.lexpos(1))
    else:
        p[0] = CicloLoop(p[4], p[1], p.lineno(1), p.lexpos(1))

def p_instruccion_asignacion(p):
    '''instruccion_asignacion : ID IGUAL expresion PUNTO_COMA
                              | ID MAS_IGUAL expresion PUNTO_COMA
                              | ID MENOS_IGUAL expresion PUNTO_COMA
                              | ID POR_IGUAL expresion PUNTO_COMA
                              | ID DIV_IGUAL expresion PUNTO_COMA
                              | ID MOD_IGUAL expresion PUNTO_COMA'''
    if p[2] == '=':
        p[0] = AsignacionVariable(p[1], p[3], p.lineno(1), p.lexpos(1))
    else:
        operador_real = p[2][0]
        acceso_var = AccesoVariable(p[1], p.lineno(1), p.lexpos(1))
        operacion = OperacionBinaria(operador_real, acceso_var, p[3], p.lineno(1), p.lexpos(1))
        p[0] = AsignacionVariable(p[1], operacion, p.lineno(1), p.lexpos(1))

def p_instruccion_imprimir(p):
    '''instruccion_imprimir : R_PRINTLN NOT PAR_IZQ argumentos PAR_DER PUNTO_COMA
                            | R_PRINTLN PAR_IZQ argumentos PAR_DER PUNTO_COMA'''
    args = p[4] if len(p) == 7 else p[3]
    p[0] = Imprimir(args, p.lineno(1), p.lexpos(1))

def p_instruccion_if(p):
    '''instruccion_if : R_IF expresion_sin_struct bloque R_ELSE bloque
                     | R_IF expresion_sin_struct bloque R_ELSE instruccion_if
                     | R_IF expresion_sin_struct bloque'''
    if len(p) == 6:
        p[0] = SentenciaIf(p[2], p[3], p[5], p.lineno(1), p.lexpos(1))
    else:
        p[0] = SentenciaIf(p[2], p[3], None, p.lineno(1), p.lexpos(1))

def p_instruccion_while(p):
    '''instruccion_while : R_WHILE expresion_sin_struct bloque'''
    p[0] = CicloWhile(p[2], p[3], p.lineno(1), p.lexpos(1))

def p_instruccion_break(p):
    '''instruccion_break : R_BREAK PUNTO_COMA
                         | R_BREAK ETIQUETA PUNTO_COMA'''
    etiqueta = p[2] if len(p) == 4 else None
    p[0] = SentenciaBreak(etiqueta, p.lineno(1), p.lexpos(1))

def p_instruccion_continue(p):
    '''instruccion_continue : R_CONTINUE PUNTO_COMA
                            | R_CONTINUE ETIQUETA PUNTO_COMA'''
    etiqueta = p[2] if len(p) == 4 else None
    p[0] = SentenciaContinue(etiqueta, p.lineno(1), p.lexpos(1))

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
    '''instruccion_struct : R_STRUCT ID LLAVE_IZQ campos_struct LLAVE_DER
                          | R_STRUCT ID LLAVE_IZQ campos_struct COMA LLAVE_DER'''
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
    '''caso_match : expresion FLECHA_DOBLE bloque
               | expresion FLECHA_DOBLE expresion'''
    if isinstance(p[3], Bloque):
        p[0] = CasoMatch(p[1], p[3])
    else:
        p[0] = CasoMatch(p[1], Bloque([p[3]], p.lineno(3), p.lexpos(3)))

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
            | R_CHAR
            | COR_IZQ tipo COR_DER
            | COR_IZQ tipo PUNTO_COMA ENTERO COR_DER
            | ID
            | ID MENOR_QUE AMPERSAND ID MAYOR_QUE'''
    if len(p) == 4:
        p[0] = f"[{p[2]}]"
    elif len(p) == 6:
        if p[1] == '[':
            p[0] = f"[{p[2]}]"
        else:
            p[0] = "[String]"
    else:
        p[0] = p[1]

def p_expresion(p):
    '''expresion : expresion_sin_struct
                 | ID LLAVE_IZQ valores_campos LLAVE_DER
                 | ID LLAVE_IZQ valores_campos COMA LLAVE_DER'''
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
                            | CARACTER
                            | R_TRUE
                            | R_FALSE'''
    tipo_token = p.slice[1].type
    if tipo_token == 'ENTERO':
        p[0] = Primitivo(int(p[1]), 'i32', p.lineno(1), p.lexpos(1))
    elif tipo_token == 'DECIMAL':
        p[0] = Primitivo(float(p[1]), 'f64', p.lineno(1), p.lexpos(1))
    elif tipo_token == 'R_TRUE':
        p[0] = Primitivo(True, 'bool', p.lineno(1), p.lexpos(1))
    elif tipo_token == 'R_FALSE':
        p[0] = Primitivo(False, 'bool', p.lineno(1), p.lexpos(1))
    elif tipo_token == 'CARACTER':
        p[0] = Primitivo(str(p[1]).replace("'", ""), 'char', p.lineno(1), p.lexpos(1))
    else:
        p[0] = Primitivo(str(p[1]), 'String', p.lineno(1), p.lexpos(1))

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
                             | expresion_sin_struct OR expresion_sin_struct
                             | expresion_sin_struct AMPERSAND expresion_sin_struct'''
    p[0] = OperacionBinaria(p[2], p[1], p[3], p.lineno(2), p.lexpos(2))

def p_expresion_acceso_arreglo(p):
    '''expresion_sin_struct : expresion_sin_struct COR_IZQ expresion COR_DER'''
    p[0] = AccesoArreglo(p[1], p[3], p.lineno(2), p.lexpos(2))

def p_expresion_acceso_y_metodos(p):
    '''expresion_sin_struct : expresion_sin_struct PUNTO ID
                            | expresion_sin_struct PUNTO ID PAR_IZQ PAR_DER
                            | expresion_sin_struct PUNTO ID PAR_IZQ argumentos PAR_DER'''
    if len(p) == 4:
        p[0] = AccesoAtributo(p[1], p[3], p.lineno(2), p.lexpos(2))
    elif len(p) == 6:
        if p[3] == 'len':
            p[0] = MetodoLen(p[1], p.lineno(2), p.lexpos(2))
        else:
            p[0] = LlamadaMetodoString(p[1], p[3], [], p.lineno(2), p.lexpos(2))
    elif len(p) == 7:
        p[0] = LlamadaMetodoString(p[1], p[3], p[5], p.lineno(2), p.lexpos(2))

def p_expresion_string_from(p):
    '''expresion_sin_struct : R_STRING CUATRO_PUNTOS ID PAR_IZQ expresion_sin_struct PAR_DER
                            | ID CUATRO_PUNTOS ID PAR_IZQ expresion_sin_struct PAR_DER
                            | R_STRING CUATRO_PUNTOS ID PAR_IZQ PAR_DER
                            | ID CUATRO_PUNTOS ID PAR_IZQ PAR_DER'''
    if len(p) == 7:
        if p[3] == 'from':
            p[0] = p[5]
    elif len(p) == 6:
        if p[3] == 'new':
            p[0] = CrearStringNuevo(p.lineno(1), p.lexpos(1))

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
                            | COR_IZQ COR_DER
                            | COR_IZQ expresion PUNTO_COMA expresion COR_DER'''
    if len(p) == 4:
        p[0] = ArregloLiteral(p[2], p.lineno(1), p.lexpos(1))
    elif len(p) == 3:
        p[0] = ArregloLiteral([], p.lineno(1), p.lexpos(1))
    elif len(p) == 6:
        p[0] = ArregloRepeticion(p[2], p[4], p.lineno(1), p.lexpos(1))

def p_expresion_slice(p):
    '''expresion_sin_struct : AMPERSAND expresion_sin_struct COR_IZQ expresion PUNTO_PUNTO expresion COR_DER'''
    p[0] = SliceArreglo(p[2], p[4], p[6], p.lineno(1), p.lexpos(1))

def p_elementos(p):
    '''elementos : elementos COMA expresion
                  | expresion'''
    if len(p) == 4:
        p[0] = p[1] + [p[3]]
    else:
        p[0] = [p[1]]

def p_error(p):
    if p:
        errores_sintacticos.append({
            'tipo': 'Sintáctico',
            'descripcion': f"Se esperaba un token válido, pero se encontró '{p.value}'",
            'linea': p.lineno,
            'columna': p.lexpos
        })
        parser.errok()
    else:
        errores_sintacticos.append({
            'tipo': 'Sintáctico',
            'descripcion': "Fin de archivo inesperado",
            'linea': "Fin",
            'columna': "Fin"
        })

def p_instruccion_expresion_suelta(p):
    '''instruccion : expresion PUNTO_COMA'''
    p[0] = p[1]

def p_expresion_unaria(p):
    '''expresion_sin_struct : MENOS expresion_sin_struct %prec UMENOS
                            | NOT expresion_sin_struct %prec NOT'''
    p[0] = OperacionUnaria(p[1], p[2], p.lineno(1), p.lexpos(1))

def p_expresion_agrupacion(p):
    '''expresion_sin_struct : PAR_IZQ expresion_sin_struct PAR_DER'''
    p[0] = p[2]

def p_instruccion_metodo_suelto(p):
    '''instruccion : ID PUNTO ID PAR_IZQ argumentos PAR_DER PUNTO_COMA
                   | ID PUNTO ID PAR_IZQ PAR_DER PUNTO_COMA'''
    acceso = AccesoVariable(p[1], p.lineno(1), p.lexpos(1))
    if len(p) == 8:
        p[0] = LlamadaMetodoString(acceso, p[3], p[5], p.lineno(2), p.lexpos(2))
    else:
        if p[3] == 'len':
            p[0] = MetodoLen(acceso, p.lineno(2), p.lexpos(2))
        else:
            p[0] = LlamadaMetodoString(acceso, p[3], [], p.lineno(2), p.lexpos(2))

parser = yacc.yacc(write_tables=False, debug=False)