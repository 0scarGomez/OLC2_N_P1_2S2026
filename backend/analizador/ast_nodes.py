class ResultadoObtenido:
    def __init__(self, valor, tipo):
        self.valor = valor
        self.tipo = tipo

class NodoAST:
    def __init__(self, linea, columna):
        self.linea = linea
        self.columna = columna

class Instruccion(NodoAST):
    pass

class Expresion(NodoAST):
    pass

class Primitivo(Expresion):
    def __init__(self, valor, tipo, linea, columna):
        super().__init__(linea, columna)
        self.valor = valor
        self.tipo = tipo

    def ejecutar(self, entorno):
        return ResultadoObtenido(self.valor, self.tipo)

class OperacionBinaria(Expresion):
    def __init__(self, operador, izq, der, linea, columna):
        super().__init__(linea, columna)
        self.operador = operador
        self.izq = izq
        self.der = der

    def ejecutar(self, entorno):
        # 1. Ejecutamos SIEMPRE el lado izquierdo primero
        izq = self.izq.ejecutar(entorno)
        
        if izq is None or izq.tipo == "None":
            return ResultadoObtenido(None, "None")

        # ==========================================
        # LÓGICA DE CORTOCIRCUITO (&&, ||)
        # ==========================================
        if self.operador == '&&':
            if izq.tipo != 'bool':
                print(f"[Error Semántico] Línea {self.linea}: Operador '&&' requiere bool, encontrado {izq.tipo}.")
                return ResultadoObtenido(None, "None")
            if not izq.valor:
                # Si el izquierdo es Falso, retornamos Falso de inmediato (No evaluamos la derecha)
                return ResultadoObtenido(False, 'bool')
                
            der = self.der.ejecutar(entorno)
            if der is None or der.tipo != 'bool':
                print(f"[Error Semántico] Línea {self.linea}: Operador '&&' requiere bool.")
                return ResultadoObtenido(None, "None")
            return ResultadoObtenido(der.valor, 'bool')

        elif self.operador == '||':
            if izq.tipo != 'bool':
                print(f"[Error Semántico] Línea {self.linea}: Operador '||' requiere bool, encontrado {izq.tipo}.")
                return ResultadoObtenido(None, "None")
            if izq.valor:
                # Si el izquierdo es Verdadero, retornamos Verdadero de inmediato (No evaluamos la derecha)
                return ResultadoObtenido(True, 'bool')
                
            der = self.der.ejecutar(entorno)
            if der is None or der.tipo != 'bool':
                print(f"[Error Semántico] Línea {self.linea}: Operador '||' requiere bool.")
                return ResultadoObtenido(None, "None")
            return ResultadoObtenido(der.valor, 'bool')

        # ==========================================
        # OTROS OPERADORES (Aritméticos y Relacionales)
        # ==========================================
        # Para el resto de operadores matemáticos, SÍ es obligatorio evaluar el lado derecho
        der = self.der.ejecutar(entorno)
        if der is None or der.tipo == "None":
            return ResultadoObtenido(None, "None")

        es_num_izq = izq.tipo in ['i32', 'f64']
        es_num_der = der.tipo in ['i32', 'f64']
        ambos_num = es_num_izq and es_num_der
        tipo_resultante = 'f64' if izq.tipo == 'f64' or der.tipo == 'f64' else 'i32'

        # -- Aritméticos --
        if self.operador == '+':
            if ambos_num:
                val = izq.valor + der.valor
                return ResultadoObtenido(float(val) if tipo_resultante == 'f64' else int(val), tipo_resultante)
            elif izq.tipo == 'String' and der.tipo == 'String':
                return ResultadoObtenido(str(izq.valor) + str(der.valor), 'String')
            else:
                print(f"[Error Semántico] Línea {self.linea}\nNo es posible aplicar '+' entre {izq.tipo} y {der.tipo}.")
                return ResultadoObtenido(None, "None")

        elif self.operador == '-':
            if ambos_num:
                val = izq.valor - der.valor
                return ResultadoObtenido(float(val) if tipo_resultante == 'f64' else int(val), tipo_resultante)
            else:
                print(f"[Error Semántico] Línea {self.linea}\nNo es posible aplicar '-' entre {izq.tipo} y {der.tipo}.")
                return ResultadoObtenido(None, "None")

        elif self.operador == '*':
            if ambos_num:
                val = izq.valor * der.valor
                return ResultadoObtenido(float(val) if tipo_resultante == 'f64' else int(val), tipo_resultante)
            elif izq.tipo == 'String' and der.tipo == 'i32':
                return ResultadoObtenido(str(izq.valor) * int(der.valor), 'String')
            elif izq.tipo == 'i32' and der.tipo == 'String':
                return ResultadoObtenido(str(der.valor) * int(izq.valor), 'String')
            else:
                print(f"[Error Semántico] Línea {self.linea}\nNo es posible aplicar '*' entre {izq.tipo} y {der.tipo}.")
                return ResultadoObtenido(None, "None")

        elif self.operador == '/':
            if ambos_num:
                if der.valor == 0:
                    print(f"[Error Semántico] Línea {self.linea}\nDivisión entre cero.")
                    return ResultadoObtenido(None, "None")
                val = izq.valor / der.valor
                return ResultadoObtenido(float(val) if tipo_resultante == 'f64' else int(val), tipo_resultante)
            else:
                print(f"[Error Semántico] Línea {self.linea}\nNo es posible aplicar '/' entre {izq.tipo} y {der.tipo}.")
                return ResultadoObtenido(None, "None")

        elif self.operador == '%':
            if ambos_num:
                if der.valor == 0:
                    print(f"[Error Semántico] Línea {self.linea}\nMódulo entre cero.")
                    return ResultadoObtenido(None, "None")
                val = izq.valor % der.valor
                return ResultadoObtenido(float(val) if tipo_resultante == 'f64' else int(val), tipo_resultante)
            else:
                print(f"[Error Semántico] Línea {self.linea}\nNo es posible aplicar '%' entre {izq.tipo} y {der.tipo}.")
                return ResultadoObtenido(None, "None")

        # -- Relacionales --
        elif self.operador in ['==', '!=', '>', '<', '>=', '<=']:
            val_izq = izq.valor
            val_der = der.valor
            tipos_validos = False

            if ambos_num:
                tipos_validos = True
            elif izq.tipo == 'bool' and der.tipo == 'bool' and self.operador in ['==', '!=']:
                tipos_validos = True
            elif izq.tipo == 'String' and der.tipo == 'String':
                tipos_validos = True
            elif izq.tipo == 'char' and der.tipo == 'char':
                tipos_validos = True
            elif (izq.tipo == 'i32' and der.tipo == 'char') or (izq.tipo == 'char' and der.tipo == 'i32'):
                tipos_validos = True
                if izq.tipo == 'char' and isinstance(val_izq, str): val_izq = ord(val_izq)
                if der.tipo == 'char' and isinstance(val_der, str): val_der = ord(val_der)

            if tipos_validos:
                if self.operador == '==': res = val_izq == val_der
                elif self.operador == '!=': res = val_izq != val_der
                elif self.operador == '>': res = val_izq > val_der
                elif self.operador == '<': res = val_izq < val_der
                elif self.operador == '>=': res = val_izq >= val_der
                elif self.operador == '<=': res = val_izq <= val_der
                return ResultadoObtenido(res, 'bool')
            else:
                print(f"[Error Semántico] Línea {self.linea}\nOperador '{self.operador}' no soportado entre {izq.tipo} y {der.tipo}.")
                return ResultadoObtenido(None, "None")

        print(f"[Error Semántico] Línea {self.linea}\nOperador '{self.operador}' desconocido.")
        return ResultadoObtenido(None, "None")

class OperacionUnaria(Expresion):
    def __init__(self, operador, operando, linea, columna):
        super().__init__(linea, columna)
        self.operador = operador
        self.operando = operando

    def ejecutar(self, entorno):
        op = self.operando.ejecutar(entorno)
        
        if op is None or op.tipo == "None":
            return ResultadoObtenido(None, "None")

        if self.operador == '-':
            if op.tipo in ['i32', 'f64']:
                val = -op.valor
                return ResultadoObtenido(float(val) if op.tipo == 'f64' else int(val), op.tipo)
            else:
                print(f"[Error Semántico] Línea {self.linea}, Columna {self.columna}\nNo es posible aplicar el operador unario '-' al tipo {op.tipo}.")
                return ResultadoObtenido(None, "None")
                
        elif self.operador == '!':
            if op.tipo == 'bool':
                return ResultadoObtenido(not op.valor, 'bool')
            else:
                print(f"[Error Semántico] Línea {self.linea}, Columna {self.columna}\nNo es posible aplicar el operador unario '!' al tipo {op.tipo}.")
                return ResultadoObtenido(None, "None")

        return ResultadoObtenido(None, "None")
    
class DeclaracionVariable(Instruccion):
    def __init__(self, es_mutable, identificador, tipo, expresion, linea, columna):
        super().__init__(linea, columna)
        self.es_mutable = es_mutable
        self.identificador = identificador
        self.tipo = tipo
        self.expresion = expresion

    def ejecutar(self, entorno):
        # Si no hay expresión de inicialización, se asigna el valor por defecto
        if self.expresion is None:
            if self.tipo == 'i32':
                valor_final = 0
            elif self.tipo == 'f64':
                valor_final = 0.0
            elif self.tipo == 'bool':
                valor_final = False
            elif self.tipo == 'String':
                valor_final = ""
            else:
                valor_final = None # Para char o arreglos sin defecto explícito
            
            tipo_variable = self.tipo
        else:
            resultado_exp = self.expresion.ejecutar(entorno)
            if resultado_exp is None: 
                return None
            
            # Inferencia de tipo si no vino explícito
            tipo_variable = self.tipo if self.tipo is not None else resultado_exp.tipo

            if self.tipo is not None and self.tipo != resultado_exp.tipo and resultado_exp.tipo != "None":
                mensaje = f"No es posible asignar un valor de tipo {resultado_exp.tipo} a una variable de tipo {self.tipo}."
                print(f"[Error Semántico] Línea {self.linea}\n{mensaje}")
                return None
                
            valor_final = resultado_exp.valor

        from backend.analizador.tabla_simbolos import Simbolo
        nuevo_simbolo = Simbolo(
            self.identificador, tipo_variable, valor_final, 
            self.es_mutable, entorno.nombre_ambito, self.linea, self.columna
        )
        entorno.guardar_variable(self.identificador, nuevo_simbolo)
        
class Imprimir(Instruccion):
    def __init__(self, argumentos, linea, columna):
        super().__init__(linea, columna)
        self.argumentos = argumentos

    def formatear_valor(self, val):
        if isinstance(val, bool):
            return "true" if val else "false"
        return str(val)

    def ejecutar(self, entorno):
        val_args = [self.formatear_valor(arg.ejecutar(entorno).valor) for arg in self.argumentos]
        if not val_args:
            print(">")
            return
        if len(val_args) == 1:
            print(f"> {val_args[0]}")
        else:
            formato = val_args[0]
            for val in val_args[1:]:
                if "{:?}" in formato:
                    formato = formato.replace("{:?}", val, 1)
                else:
                    formato = formato.replace("{}", val, 1)
            print(f"> {formato}")
            
class AccesoVariable(Expresion):
    def __init__(self, identificador, linea, columna):
        super().__init__(linea, columna)
        self.identificador = identificador

    def ejecutar(self, entorno):
        simbolo = entorno.obtener_variable(self.identificador)
        if simbolo is None:
            mensaje = f"La variable '{self.identificador}' no ha sido declarada."
            print(f"[Error Semántico] Línea {self.linea}, Columna {self.columna}\n{mensaje}")
            return ResultadoObtenido("None", "None")
        return ResultadoObtenido(simbolo.valor, simbolo.tipo)
    
class Bloque(Instruccion):
    def __init__(self, instrucciones, linea, columna):
        super().__init__(linea, columna)
        self.instrucciones = instrucciones

    def ejecutar(self, entorno):
        from backend.analizador.tabla_simbolos import Entorno
        nuevo_entorno = Entorno(anterior=entorno, nombre_ambito="Bloque")
        for inst in self.instrucciones:
            if inst:
                inst.ejecutar(nuevo_entorno)

class SentenciaIf(Instruccion):
    def __init__(self, condicion, bloque_if, bloque_else, linea, columna):
        super().__init__(linea, columna)
        self.condicion = condicion
        self.bloque_if = bloque_if
        self.bloque_else = bloque_else

    def ejecutar(self, entorno):
        cond = self.condicion.ejecutar(entorno)
        if cond.tipo != 'bool':
            mensaje = f"La condición del 'if' debe ser de tipo bool, pero se encontró {cond.tipo}."
            print(f"[Error Semántico] Línea {self.linea}\n{mensaje}")
            return None

        if cond.valor is True:
            self.bloque_if.ejecutar(entorno)
        elif self.bloque_else is not None:
            self.bloque_else.ejecutar(entorno)
            
class AsignacionVariable(Instruccion):
    def __init__(self, identificador, expresion, linea, columna):
        super().__init__(linea, columna)
        self.identificador = identificador
        self.expresion = expresion

    def ejecutar(self, entorno):
        simbolo = entorno.obtener_variable(self.identificador)
        if simbolo is None:
            mensaje = f"La variable '{self.identificador}' no ha sido declarada."
            print(f"[Error Semántico] Línea {self.linea}, Columna {self.columna}\n{mensaje}")
            return None

        val_exp = self.expresion.ejecutar(entorno)

        if simbolo.tipo != val_exp.tipo and val_exp.tipo != "None":
            mensaje = f"No se puede asignar un valor de tipo {val_exp.tipo} a la variable '{self.identificador}' de tipo {simbolo.tipo}."
            print(f"[Error Semántico] Línea {self.linea}\n{mensaje}")
            return None

        resultado = entorno.actualizar_variable(self.identificador, val_exp.valor)
        if resultado == "ERROR_INMUTABLE":
            mensaje = f"No se puede reasignar la variable inmutable '{self.identificador}'."
            print(f"[Error Semántico] Línea {self.linea}, Columna {self.columna}\n{mensaje}")

class BreakException(Exception):
    def __init__(self, etiqueta=None):
        self.etiqueta = etiqueta

class ContinueException(Exception):
    def __init__(self, etiqueta=None):
        self.etiqueta = etiqueta

class SentenciaBreak(Instruccion):
    def __init__(self, etiqueta, linea, columna):
        super().__init__(linea, columna)
        self.etiqueta = etiqueta

    def ejecutar(self, entorno):
        raise BreakException(self.etiqueta)

class SentenciaContinue(Instruccion):
    def __init__(self, etiqueta, linea, columna):
        super().__init__(linea, columna)
        self.etiqueta = etiqueta

    def ejecutar(self, entorno):
        raise ContinueException(self.etiqueta)

class CicloWhile(Instruccion):
    def __init__(self, condicion, bloque, linea, columna):
        super().__init__(linea, columna)
        self.condicion = condicion
        self.bloque = bloque

    def ejecutar(self, entorno):
        while True:
            cond = self.condicion.ejecutar(entorno)
            if cond.tipo != 'bool':
                print(f"[Error Semántico] Línea {self.linea}: La condición del 'while' debe ser bool.")
                break

            if cond.valor is True:
                try:
                    self.bloque.ejecutar(entorno)
                except BreakException:
                    break
                except ContinueException:
                    continue
            else:
                break
            
class ReturnException(Exception):
    def __init__(self, resultado):
        self.resultado = resultado

class SentenciaReturn(Instruccion):
    def __init__(self, expresion, linea, columna):
        super().__init__(linea, columna)
        self.expresion = expresion

    def ejecutar(self, entorno):
        val = self.expresion.ejecutar(entorno) if self.expresion else ResultadoObtenido(None, "void")
        raise ReturnException(val)
    
class DeclaracionFuncion(Instruccion):
    def __init__(self, nombre, parametros, tipo_retorno, bloque, linea, columna):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.parametros = parametros
        self.tipo_retorno = tipo_retorno
        self.bloque = bloque

    def ejecutar(self, entorno):
        from backend.analizador.tabla_simbolos import Simbolo
        simbolo_fn = Simbolo(
            self.nombre, "Funcion", self, False, entorno.nombre_ambito, self.linea, self.columna
        )
        entorno.guardar_variable(self.nombre, simbolo_fn)

class LlamadaFuncion(Expresion):
    def __init__(self, nombre, argumentos, linea, columna):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.argumentos = argumentos

    def ejecutar(self, entorno):
        simbolo = entorno.obtener_variable(self.nombre)
        if not simbolo or simbolo.tipo != "Funcion":
            print(f"[Error Semántico] Línea {self.linea}: La función '{self.nombre}' no está definida.")
            return ResultadoObtenido("None", "None")

        simbolo_fn = simbolo.valor

        if len(self.argumentos) != len(simbolo_fn.parametros):
            print(f"[Error Semántico] Línea {self.linea}: Esperados {len(simbolo_fn.parametros)} argumentos, pero se recibieron {len(self.argumentos)}.")
            return ResultadoObtenido("None", "None")

        from backend.analizador.tabla_simbolos import Entorno, Simbolo
        entorno_local = Entorno(anterior=entorno, nombre_ambito=f"Funcion_{self.nombre}")

        for (param_id, param_tipo), arg_exp in zip(simbolo_fn.parametros, self.argumentos):
            arg_val = arg_exp.ejecutar(entorno)
            if arg_val.tipo != param_tipo:
                print(f"[Error Semántico] Línea {self.linea}: El argumento '{param_id}' debe ser de tipo {param_tipo}.")
                return ResultadoObtenido("None", "None")
            
            param_simbolo = Simbolo(param_id, param_tipo, arg_val.valor, True, entorno_local.nombre_ambito, self.linea, self.columna)
            entorno_local.guardar_variable(param_id, param_simbolo)

        try:
            simbolo_fn.bloque.ejecutar(entorno_local)
        except ReturnException as ret:
            if simbolo_fn.tipo_retorno and ret.resultado.tipo != simbolo_fn.tipo_retorno:
                print(f"[Error Semántico] Línea {self.linea}: Tipo de retorno incorrecto en '{self.nombre}'.")
                return ResultadoObtenido("None", "None")
            return ret.resultado

        return ResultadoObtenido(None, "void")
    
class ArregloLiteral(Expresion):
    def __init__(self, elementos, linea, columna):
        super().__init__(linea, columna)
        self.elementos = elementos

    def ejecutar(self, entorno):
        valores = []
        tipo_elem = None
        for elem in self.elementos:
            res = elem.ejecutar(entorno)
            if tipo_elem is None:
                tipo_elem = res.tipo
            elif tipo_elem != res.tipo:
                print(f"[Error Semántico] Línea {self.linea}: Elementos del arreglo con tipos inconsistentes.")
                return ResultadoObtenido("None", "None")
            valores.append(res.valor)
        return ResultadoObtenido(valores, f"[{tipo_elem if tipo_elem else 'any'}]")

class AccesoArreglo(Expresion):
    def __init__(self, arreglo, indice, linea, columna):
        super().__init__(linea, columna)
        self.arreglo = arreglo
        self.indice = indice

    def ejecutar(self, entorno):
        arr_res = self.arreglo.ejecutar(entorno)
        idx_res = self.indice.ejecutar(entorno)

        if idx_res.tipo != 'i32':
            print(f"[Error Semántico] Línea {self.linea}: El índice debe ser de tipo i32.")
            return ResultadoObtenido("None", "None")

        if not isinstance(arr_res.valor, list):
            print(f"[Error Semántico] Línea {self.linea}: La expresión no es un arreglo.")
            return ResultadoObtenido("None", "None")

        try:
            val = arr_res.valor[idx_res.valor]
            tipo_interno = arr_res.tipo.strip('[]')
            return ResultadoObtenido(val, tipo_interno)
        except IndexError:
            print(f"[Error Semántico] Línea {self.linea}: Índice fuera de rango ({idx_res.valor}).")
            return ResultadoObtenido("None", "None")

class AsignacionArreglo(Instruccion):
    def __init__(self, identificador, indice, expresion, linea, columna):
        super().__init__(linea, columna)
        self.identificador = identificador
        self.indice = indice
        self.expresion = expresion

    def ejecutar(self, entorno):
        simbolo = entorno.obtener_variable(self.identificador)
        if not simbolo:
            print(f"[Error Semántico] Línea {self.linea}: Variable '{self.identificador}' no declarada.")
            return

        idx_res = self.indice.ejecutar(entorno)
        val_res = self.expresion.ejecutar(entorno)

        if idx_res.tipo != 'i32':
            print(f"[Error Semántico] Línea {self.linea}: El índice debe ser de tipo i32.")
            return

        if not isinstance(simbolo.valor, list):
            print(f"[Error Semántico] Línea {self.linea}: Variable '{self.identificador}' no es un arreglo.")
            return

        tipo_interno = simbolo.tipo.strip('[]')
        if val_res.tipo != tipo_interno:
            print(f"[Error Semántico] Línea {self.linea}: Tipo {val_res.tipo} incompatible con el arreglo de tipo {tipo_interno}.")
            return

        try:
            simbolo.valor[idx_res.valor] = val_res.valor
        except IndexError:
            print(f"[Error Semántico] Línea {self.linea}: Índice fuera de rango ({idx_res.valor}).")

class DeclaracionStruct(Instruccion):
    def __init__(self, nombre, campos, linea, columna):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.campos = campos

    def ejecutar(self, entorno):
        from backend.analizador.tabla_simbolos import Simbolo
        simbolo = Simbolo(self.nombre, "StructDef", self.campos, False, entorno.nombre_ambito, self.linea, self.columna)
        entorno.guardar_variable(self.nombre, simbolo)

class InstanciacionStruct(Expresion):
    def __init__(self, nombre_struct, valores_campos, linea, columna):
        super().__init__(linea, columna)
        self.nombre_struct = nombre_struct
        self.valores_campos = valores_campos

    def ejecutar(self, entorno):
        struct_def = entorno.obtener_variable(self.nombre_struct)
        if not struct_def or struct_def.tipo != "StructDef":
            print(f"[Error Semántico] Línea {self.linea}: El struct '{self.nombre_struct}' no ha sido definido.")
            return ResultadoObtenido("None", "None")

        campos_def = struct_def.valor
        instancia_valores = {}

        for campo_nom, exp in self.valores_campos.items():
            if campo_nom not in campos_def:
                print(f"[Error Semántico] Línea {self.linea}: El campo '{campo_nom}' no existe en '{self.nombre_struct}'.")
                return ResultadoObtenido("None", "None")

            res = exp.ejecutar(entorno)
            tipo_esperado = campos_def[campo_nom]
            if res.tipo != tipo_esperado:
                print(f"[Error Semántico] Línea {self.linea}: Tipo incorrecto para '{campo_nom}'. Esperado {tipo_esperado}, obtenido {res.tipo}.")
                return ResultadoObtenido("None", "None")

            instancia_valores[campo_nom] = res.valor

        return ResultadoObtenido(instancia_valores, self.nombre_struct)

class AccesoAtributo(Expresion):
    def __init__(self, expresion, atributo, linea, columna):
        super().__init__(linea, columna)
        self.expresion = expresion
        self.atributo = atributo

    def ejecutar(self, entorno):
        obj_res = self.expresion.ejecutar(entorno)
        if not isinstance(obj_res.valor, dict):
            print(f"[Error Semántico] Línea {self.linea}: Intentando acceder a atributo de un elemento no struct.")
            return ResultadoObtenido("None", "None")

        if self.atributo not in obj_res.valor:
            print(f"[Error Semántico] Línea {self.linea}: El atributo '{self.atributo}' no existe en el struct.")
            return ResultadoObtenido("None", "None")

        return ResultadoObtenido(obj_res.valor[self.atributo], "any")

class AsignacionAtributo(Instruccion):
    def __init__(self, identificador, atributo, expresion, linea, columna):
        super().__init__(linea, columna)
        self.identificador = identificador
        self.atributo = atributo
        self.expresion = expresion

    def ejecutar(self, entorno):
        simbolo = entorno.obtener_variable(self.identificador)
        if not simbolo:
            print(f"[Error Semántico] Línea {self.linea}: Variable '{self.identificador}' no declarada.")
            return

        if not isinstance(simbolo.valor, dict):
            print(f"[Error Semántico] Línea {self.linea}: '{self.identificador}' no es un struct.")
            return

        if self.atributo not in simbolo.valor:
            print(f"[Error Semántico] Línea {self.linea}: Atributo '{self.atributo}' no existe.")
            return

        val_res = self.expresion.ejecutar(entorno)
        simbolo.valor[self.atributo] = val_res.valor

class MetodoLen(Expresion):
    def __init__(self, expresion, linea, columna):
        super().__init__(linea, columna)
        self.expresion = expresion

    def ejecutar(self, entorno):
        res = self.expresion.ejecutar(entorno)
        if isinstance(res.valor, (list, str)):
            return ResultadoObtenido(len(res.valor), 'i32')
        print(f"[Error Semántico] Línea {self.linea}: El tipo {res.tipo} no posee el método .len().")
        return ResultadoObtenido("None", "None")

class CasoMatch:
    def __init__(self, patron, bloque):
        self.patron = patron
        self.bloque = bloque

class SentenciaMatch(Instruccion):
    def __init__(self, expresion, casos, linea, columna):
        super().__init__(linea, columna)
        self.expresion = expresion
        self.casos = casos

    def ejecutar(self, entorno):
        val_match = self.expresion.ejecutar(entorno)
        if val_match.tipo == "None":
            return

        for caso in self.casos:
            if isinstance(caso.patron, AccesoVariable) and caso.patron.identificador == '_':
                caso.bloque.ejecutar(entorno)
                break

            val_patron = caso.patron.ejecutar(entorno)
            if val_match.valor == val_patron.valor:
                caso.bloque.ejecutar(entorno)
                break

class CicloLoop(Instruccion):
    def __init__(self, bloque, etiqueta, linea, columna):
        super().__init__(linea, columna)
        self.bloque = bloque
        self.etiqueta = etiqueta

    def ejecutar(self, entorno):
        while True:
            try:
                res = self.bloque.ejecutar(entorno)
                if res is not None and hasattr(res, 'tipo') and res.tipo == 'return':
                    return res
            except BreakException as b:
                # Si no tiene etiqueta, o la etiqueta coincide con este loop, rompemos aquí
                if b.etiqueta is None or b.etiqueta == self.etiqueta:
                    break
                else:
                    raise b  # Pertenece a un loop más externo, seguimos propagando el error
            except ContinueException as c:
                if c.etiqueta is None or c.etiqueta == self.etiqueta:
                    continue
                else:
                    raise c
                
class ArregloRepeticion(Expresion):
    def __init__(self, valor, cantidad, linea, columna):
        super().__init__(linea, columna)
        self.valor = valor
        self.cantidad = cantidad

    def ejecutar(self, entorno):
        res_val = self.valor.ejecutar(entorno)
        res_cant = self.cantidad.ejecutar(entorno)

        if res_cant.tipo != 'i32':
            print(f"[Error Semántico] Línea {self.linea}: La cantidad del arreglo debe ser i32.")
            return ResultadoObtenido("None", "None")

        # Se crea un arreglo repitiendo el valor evaluado
        lista = [res_val.valor] * res_cant.valor
        return ResultadoObtenido(lista, f"[{res_val.tipo}]")

class SliceArreglo(Expresion):
    def __init__(self, arreglo, inicio, fin, linea, columna):
        super().__init__(linea, columna)
        self.arreglo = arreglo
        self.inicio = inicio
        self.fin = fin

    def ejecutar(self, entorno):
        res_arr = self.arreglo.ejecutar(entorno)
        res_inicio = self.inicio.ejecutar(entorno)
        res_fin = self.fin.ejecutar(entorno)

        if res_inicio.tipo != 'i32' or res_fin.tipo != 'i32':
            print(f"[Error Semántico] Línea {self.linea}: Los índices del slice deben ser i32.")
            return ResultadoObtenido("None", "None")

        if not isinstance(res_arr.valor, list):
            print(f"[Error Semántico] Línea {self.linea}: Solo se pueden crear slices de arreglos.")
            return ResultadoObtenido("None", "None")

        # Retornamos el segmento de la lista en Python
        segmento = res_arr.valor[res_inicio.valor:res_fin.valor]
        return ResultadoObtenido(segmento, res_arr.tipo)
    
class CrearStringNuevo(Expresion):
    def __init__(self, linea, columna):
        super().__init__(linea, columna)

    def ejecutar(self, entorno):
        return ResultadoObtenido("", "String")

class LlamadaMetodoString(Expresion):
    def __init__(self, objeto, metodo, argumentos, linea, columna):
        super().__init__(linea, columna)
        self.objeto = objeto
        self.metodo = metodo
        self.argumentos = argumentos

    def ejecutar(self, entorno):
        res_obj = self.objeto.ejecutar(entorno)
        val_args = [arg.ejecutar(entorno).valor for arg in self.argumentos]

        # 1. Si el objeto principal es una cadena de texto (String)
        if isinstance(res_obj.valor, str):
            if self.metodo == 'replace':
                if len(val_args) != 2:
                    print(f"[Error Semántico] Línea {self.linea}: replace() requiere 2 argumentos.")
                    return ResultadoObtenido("None", "None")
                nuevo_texto = res_obj.valor.replace(str(val_args[0]), str(val_args[1]))
                return ResultadoObtenido(nuevo_texto, "String")
            
            elif self.metodo == 'split_whitespace':
                # Divide la cadena por espacios y retorna la lista
                palabras = res_obj.valor.split()
                return ResultadoObtenido(palabras, "[String]")

        # 2. Si el objeto principal ya es una lista (ej. para encadenar .collect())
        elif isinstance(res_obj.valor, list):
            if self.metodo == 'collect':
                # collect agrupa el iterador en Rust; aquí simplemente devolvemos la lista que ya tenemos
                return ResultadoObtenido(res_obj.valor, res_obj.tipo)

        print(f"[Error Semántico] Línea {self.linea}: El método '{self.metodo}' no está disponible para este tipo.")
        return ResultadoObtenido("None", "None")