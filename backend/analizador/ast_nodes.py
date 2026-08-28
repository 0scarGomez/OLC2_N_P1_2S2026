# Estructura para retornar valores y sus tipos
class ResultadoObtenido:
    def __init__(self, valor, tipo):
        self.valor = valor
        self.tipo = tipo

# Clases Bases
class NodoAST:
    def __init__(self, linea, columna):
        self.linea = linea
        self.columna = columna

class Instruccion(NodoAST):
    pass

class Expresion(NodoAST):
    pass

# Nodos Específicos
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
        izq = self.izq.ejecutar(entorno)
        der = self.der.ejecutar(entorno)

        # Operadores Aritméticos
        if self.operador == '+':
            if izq.tipo == 'i32' and der.tipo == 'i32':
                return ResultadoObtenido(izq.valor + der.valor, 'i32')
            elif izq.tipo == 'f64' and der.tipo == 'f64':
                return ResultadoObtenido(izq.valor + der.valor, 'f64')
        elif self.operador == '-':
            if izq.tipo in ['i32', 'f64'] and izq.tipo == der.tipo:
                return ResultadoObtenido(izq.valor - der.valor, izq.tipo)
        elif self.operador == '*':
            if izq.tipo in ['i32', 'f64'] and izq.tipo == der.tipo:
                return ResultadoObtenido(izq.valor * der.valor, izq.tipo)
        elif self.operador == '/':
            if izq.tipo in ['i32', 'f64'] and izq.tipo == der.tipo:
                if der.valor == 0:
                    print(f"[Error Semántico] Línea {self.linea}: División entre cero.")
                    return ResultadoObtenido("None", "None")
                return ResultadoObtenido(izq.valor / der.valor, izq.tipo)

        # Operadores Relacionales
        elif self.operador in ['>', '<', '>=', '<=']:
            if izq.tipo in ['i32', 'f64'] and der.tipo in ['i32', 'f64']:
                if self.operador == '>': res = izq.valor > der.valor
                elif self.operador == '<': res = izq.valor < der.valor
                elif self.operador == '>=': res = izq.valor >= der.valor
                elif self.operador == '<=': res = izq.valor <= der.valor
                return ResultadoObtenido(res, 'bool')

        elif self.operador in ['==', '!=']:
            if izq.tipo == der.tipo:
                res = izq.valor == der.valor if self.operador == '==' else izq.valor != der.valor
                return ResultadoObtenido(res, 'bool')

        # Operadores Lógicos
        elif self.operador == '&&':
            if izq.tipo == 'bool' and der.tipo == 'bool':
                return ResultadoObtenido(izq.valor and der.valor, 'bool')
        elif self.operador == '||':
            if izq.tipo == 'bool' and der.tipo == 'bool':
                return ResultadoObtenido(izq.valor or der.valor, 'bool')

        # Error de tipos incompatibles
        mensaje = f"Operador '{self.operador}' no soportado entre tipos {izq.tipo} y {der.tipo}."
        print(f"[Error Semántico] Línea {self.linea}, Columna {self.columna}\n{mensaje}")
        return ResultadoObtenido("None", "None")

class DeclaracionVariable(Instruccion):
    def __init__(self, es_mutable, identificador, tipo, expresion, linea, columna):
        super().__init__(linea, columna)
        self.es_mutable = es_mutable
        self.identificador = identificador
        self.tipo = tipo
        self.expresion = expresion

    def ejecutar(self, entorno):
        resultado_exp = self.expresion.ejecutar(entorno)
        
        # Verificación de tipos en la asignación
        if self.tipo != resultado_exp.tipo and resultado_exp.tipo != "None":
            mensaje = f"No es posible asignar un valor de tipo {resultado_exp.tipo} a una variable de tipo {self.tipo}."
            print(f"[Error Semántico] Línea {self.linea}\n{mensaje}")
            return None

        # Si todo es correcto, guardamos el símbolo en la tabla
        from backend.analizador.tabla_simbolos import Simbolo
        nuevo_simbolo = Simbolo(
            self.identificador, self.tipo, resultado_exp.valor, 
            self.es_mutable, entorno.nombre_ambito, self.linea, self.columna
        )
        entorno.guardar_variable(self.identificador, nuevo_simbolo)
        
class Imprimir(Instruccion):
    def __init__(self, expresion, linea, columna):
        super().__init__(linea, columna)
        self.expresion = expresion

    def ejecutar(self, entorno):
        resultado = self.expresion.ejecutar(entorno)
        if resultado and resultado.tipo != "None":
            print(f"> {resultado.valor}")

class AccesoVariable(Expresion):
    def __init__(self, identificador, linea, columna):
        super().__init__(linea, columna)
        self.identificador = identificador

    def ejecutar(self, entorno):
        # Buscamos la variable en el entorno (Tabla de Símbolos)
        simbolo = entorno.obtener_variable(self.identificador)
        
        if simbolo is None:
            mensaje = f"La variable '{self.identificador}' no ha sido declarada."
            print(f"[Error Semántico] Línea {self.linea}, Columna {self.columna}\n{mensaje}")
            return ResultadoObtenido("None", "None")
            
        # Si existe, devolvemos su valor y su tipo
        return ResultadoObtenido(simbolo.valor, simbolo.tipo)
    
    
class Bloque(Instruccion):
    def __init__(self, instrucciones, linea, columna):
        super().__init__(linea, columna)
        self.instrucciones = instrucciones

    def ejecutar(self, entorno):
        # Cada bloque crea un nuevo ámbito/scope hijo
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
        
        # Validar que la condición sea booleana
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

        # Verificación de tipos
        if simbolo.tipo != val_exp.tipo and val_exp.tipo != "None":
            mensaje = f"No se puede asignar un valor de tipo {val_exp.tipo} a la variable '{self.identificador}' de tipo {simbolo.tipo}."
            print(f"[Error Semántico] Línea {self.linea}\n{mensaje}")
            return None

        # Intento de actualización 
        resultado = entorno.actualizar_variable(self.identificador, val_exp.valor)
        if resultado == "ERROR_INMUTABLE":
            mensaje = f"No se puede reasignar la variable inmutable '{self.identificador}'."
            print(f"[Error Semántico] Línea {self.linea}, Columna {self.columna}\n{mensaje}")


# Excepciones de control de flujo
class BreakException(Exception):
    pass

class ContinueException(Exception):
    pass

class SentenciaBreak(Instruccion):
    def __init__(self, linea, columna):
        super().__init__(linea, columna)

    def ejecutar(self, entorno):
        raise BreakException()

class SentenciaContinue(Instruccion):
    def __init__(self, linea, columna):
        super().__init__(linea, columna)

    def ejecutar(self, entorno):
        raise ContinueException()

# ciclo while
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
                    break  # Sale inmediatamente del bucle
                except ContinueException:
                    continue  # Pasa a la siguiente iteración
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
        self.parametros = parametros  # Lista de tuplas: (id, tipo)
        self.tipo_retorno = tipo_retorno
        self.bloque = bloque

    def ejecutar(self, entorno):
        from backend.analizador.tabla_simbolos import Simbolo
        # Empaquetamos la función como un Símbolo
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

        simbolo_fn = simbolo.valor  # Extraemos el nodo DeclaracionFuncion

        if len(self.argumentos) != len(simbolo_fn.parametros):
            print(f"[Error Semántico] Línea {self.linea}: Esperados {len(simbolo_fn.parametros)} argumentos, pero se recibieron {len(self.argumentos)}.")
            return ResultadoObtenido("None", "None")

        # Crear nuevo ámbito local
        from backend.analizador.tabla_simbolos import Entorno, Simbolo
        entorno_local = Entorno(anterior=entorno, nombre_ambito=f"Funcion_{self.nombre}")

        # Pasar parámetros al ámbito local
        for (param_id, param_tipo), arg_exp in zip(simbolo_fn.parametros, self.argumentos):
            arg_val = arg_exp.ejecutar(entorno)
            if arg_val.tipo != param_tipo:
                print(f"[Error Semántico] Línea {self.linea}: El argumento '{param_id}' debe ser de tipo {param_tipo}.")
                return ResultadoObtenido("None", "None")
            
            param_simbolo = Simbolo(param_id, param_tipo, arg_val.valor, True, entorno_local.nombre_ambito, self.linea, self.columna)
            entorno_local.guardar_variable(param_id, param_simbolo)

        # Ejecutar cuerpo de la función
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
        self.campos = campos  # Diccionario {nombre_campo: tipo_campo}

    def ejecutar(self, entorno):
        from backend.analizador.tabla_simbolos import Simbolo
        simbolo = Simbolo(self.nombre, "StructDef", self.campos, False, entorno.nombre_ambito, self.linea, self.columna)
        entorno.guardar_variable(self.nombre, simbolo)


class InstanciacionStruct(Expresion):
    def __init__(self, nombre_struct, valores_campos, linea, columna):
        super().__init__(linea, columna)
        self.nombre_struct = nombre_struct
        self.valores_campos = valores_campos  # Diccionario {nombre_campo: expresion}

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

        ejecutado = False
        for caso in self.casos:
            # Caso por defecto '_' (comodín)
            if isinstance(caso.patron, AccesoVariable) and caso.patron.identificador == '_':
                caso.bloque.ejecutar(entorno)
                ejecutado = True
                break

            val_patron = caso.patron.ejecutar(entorno)
            if val_match.valor == val_patron.valor:
                caso.bloque.ejecutar(entorno)
                ejecutado = True
                break