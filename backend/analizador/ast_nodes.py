import random

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
        izq = self.izq.ejecutar(entorno)
        if izq is None or izq.tipo == "None":
            return ResultadoObtenido(None, "None")

        if self.operador == '&&':
            if izq.tipo != 'bool':
                entorno.registrar_error("Semántico", f"Operador '&&' requiere bool, encontrado {izq.tipo}.", self.linea, self.columna)
                return ResultadoObtenido(None, "None")
            if not izq.valor:
                return ResultadoObtenido(False, 'bool')
            der = self.der.ejecutar(entorno)
            if der is None or der.tipo != 'bool':
                entorno.registrar_error("Semántico", "Operador '&&' requiere bool.", self.linea, self.columna)
                return ResultadoObtenido(None, "None")
            return ResultadoObtenido(der.valor, 'bool')

        elif self.operador == '||':
            if izq.tipo != 'bool':
                entorno.registrar_error("Semántico", f"Operador '||' requiere bool, encontrado {izq.tipo}.", self.linea, self.columna)
                return ResultadoObtenido(None, "None")
            if izq.valor:
                return ResultadoObtenido(True, 'bool')
            der = self.der.ejecutar(entorno)
            if der is None or der.tipo != 'bool':
                entorno.registrar_error("Semántico", "Operador '||' requiere bool.", self.linea, self.columna)
                return ResultadoObtenido(None, "None")
            return ResultadoObtenido(der.valor, 'bool')

        der = self.der.ejecutar(entorno)
        if der is None or der.tipo == "None":
            return ResultadoObtenido(None, "None")

        es_num_izq = izq.tipo in ['i32', 'f64']
        es_num_der = der.tipo in ['i32', 'f64']
        ambos_num = es_num_izq and es_num_der
        tipo_resultante = 'f64' if izq.tipo == 'f64' or der.tipo == 'f64' else 'i32'

        if self.operador == '+':
            if ambos_num:
                val = izq.valor + der.valor
                return ResultadoObtenido(float(val) if tipo_resultante == 'f64' else int(val), tipo_resultante)
            elif izq.tipo == 'String' and der.tipo == 'String':
                return ResultadoObtenido(str(izq.valor) + str(der.valor), 'String')
            else:
                entorno.registrar_error("Semántico", f"No es posible aplicar '+' entre {izq.tipo} y {der.tipo}.", self.linea, self.columna)
                return ResultadoObtenido(None, "None")

        elif self.operador == '-':
            if ambos_num:
                val = izq.valor - der.valor
                return ResultadoObtenido(float(val) if tipo_resultante == 'f64' else int(val), tipo_resultante)
            else:
                entorno.registrar_error("Semántico", f"No es posible aplicar '-' entre {izq.tipo} y {der.tipo}.", self.linea, self.columna)
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
                entorno.registrar_error("Semántico", f"No es posible aplicar '*' entre {izq.tipo} y {der.tipo}.", self.linea, self.columna)
                return ResultadoObtenido(None, "None")

        elif self.operador == '/':
            if ambos_num:
                if der.valor == 0:
                    entorno.registrar_error("Semántico", "División entre cero.", self.linea, self.columna)
                    return ResultadoObtenido(None, "None")
                val = izq.valor / der.valor
                return ResultadoObtenido(float(val) if tipo_resultante == 'f64' else int(val), tipo_resultante)
            else:
                entorno.registrar_error("Semántico", f"No es posible aplicar '/' entre {izq.tipo} y {der.tipo}.", self.linea, self.columna)
                return ResultadoObtenido(None, "None")

        elif self.operador == '%':
            if ambos_num:
                if der.valor == 0:
                    entorno.registrar_error("Semántico", "Módulo entre cero.", self.linea, self.columna)
                    return ResultadoObtenido(None, "None")
                val = izq.valor % der.valor
                return ResultadoObtenido(float(val) if tipo_resultante == 'f64' else int(val), tipo_resultante)
            else:
                entorno.registrar_error("Semántico", f"No es posible aplicar '%' entre {izq.tipo} y {der.tipo}.", self.linea, self.columna)
                return ResultadoObtenido(None, "None")

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
                entorno.registrar_error("Semántico", f"Operador '{self.operador}' no soportado entre {izq.tipo} y {der.tipo}.", self.linea, self.columna)
                return ResultadoObtenido(None, "None")

        entorno.registrar_error("Semántico", f"Operador '{self.operador}' desconocido.", self.linea, self.columna)
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
                entorno.registrar_error("Semántico", f"No es posible aplicar '-' al tipo {op.tipo}.", self.linea, self.columna)
                return ResultadoObtenido(None, "None")
        elif self.operador == '!':
            if op.tipo == 'bool':
                return ResultadoObtenido(not op.valor, 'bool')
            else:
                entorno.registrar_error("Semántico", f"No es posible aplicar '!' al tipo {op.tipo}.", self.linea, self.columna)
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
        if self.expresion is None:
            defaults = {'i32': 0, 'f64': 0.0, 'bool': False, 'String': ""}
            valor_final = defaults.get(self.tipo, None)
            tipo_variable = self.tipo
        else:
            resultado_exp = self.expresion.ejecutar(entorno)
            if resultado_exp is None or resultado_exp.tipo == "None": 
                return None
            tipo_variable = self.tipo if self.tipo is not None else resultado_exp.tipo
            if self.tipo is not None and self.tipo != resultado_exp.tipo:
                entorno.registrar_error("Semántico", f"No es posible asignar {resultado_exp.tipo} a {self.tipo}.", self.linea, self.columna)
                return None
            valor_final = resultado_exp.valor

        from backend.analizador.tabla_simbolos import Simbolo
        nuevo_simbolo = Simbolo(self.identificador, tipo_variable, valor_final, self.es_mutable, entorno.nombre_ambito, self.linea, self.columna)
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
        val_args = []
        for arg in self.argumentos:
            res = arg.ejecutar(entorno)
            if res is not None:
                val_args.append(self.formatear_valor(res.valor))
        
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
            entorno.registrar_error("Semántico", f"La variable '{self.identificador}' no ha sido declarada.", self.linea, self.columna)
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
        if cond is None or cond.tipo == "None":
            return None

        if cond.tipo != 'bool':
            entorno.registrar_error("Semántico", f"La condición del 'if' debe ser bool, encontrado {cond.tipo}.", self.linea, self.columna)
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
            entorno.registrar_error("Semántico", f"La variable '{self.identificador}' no ha sido declarada.", self.linea, self.columna)
            return None

        val_exp = self.expresion.ejecutar(entorno)
        if val_exp is None or val_exp.tipo == "None":
            return None

        if simbolo.tipo != val_exp.tipo:
            entorno.registrar_error("Semántico", f"No se puede asignar {val_exp.tipo} a {self.identificador} ({simbolo.tipo}).", self.linea, self.columna)
            return None

        resultado = entorno.actualizar_variable(self.identificador, val_exp.valor)
        if resultado == "ERROR_INMUTABLE":
            entorno.registrar_error("Semántico", f"No se puede reasignar variable inmutable '{self.identificador}'.", self.linea, self.columna)

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
            if cond is None or cond.tipo != 'bool':
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
        simbolo_fn = Simbolo(self.nombre, "Funcion", self, False, entorno.nombre_ambito, self.linea, self.columna)
        entorno.guardar_variable(self.nombre, simbolo_fn)

class LlamadaFuncion(Expresion):
    def __init__(self, nombre, argumentos, linea, columna):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.argumentos = argumentos

    def ejecutar(self, entorno):
        if self.nombre == 'typeof' and len(self.argumentos) == 1:
            res = self.argumentos[0].ejecutar(entorno)
            return ResultadoObtenido(res.tipo, "String")

        if self.nombre == 'random' and len(self.argumentos) == 2:
            min_val = self.argumentos[0].ejecutar(entorno).valor
            max_val = self.argumentos[1].ejecutar(entorno).valor
            return ResultadoObtenido(random.randint(int(min_val), int(max_val)), "i32")

        simbolo = entorno.obtener_variable(self.nombre)
        if not simbolo or simbolo.tipo != "Funcion":
            entorno.registrar_error("Semántico", f"La función '{self.nombre}' no está definida.", self.linea, self.columna)
            return ResultadoObtenido("None", "None")

        simbolo_fn = simbolo.valor
        if len(self.argumentos) != len(simbolo_fn.parametros):
            entorno.registrar_error("Semántico", f"Esperados {len(simbolo_fn.parametros)} argumentos en '{self.nombre}'.", self.linea, self.columna)
            return ResultadoObtenido("None", "None")

        from backend.analizador.tabla_simbolos import Entorno, Simbolo
        entorno_local = Entorno(anterior=entorno, nombre_ambito=f"Funcion_{self.nombre}")

        for (param_id, param_tipo), arg_exp in zip(simbolo_fn.parametros, self.argumentos):
            arg_val = arg_exp.ejecutar(entorno)
            if arg_val is None or arg_val.tipo == "None":
                return ResultadoObtenido("None", "None")
            if arg_val.tipo != param_tipo:
                entorno.registrar_error("Semántico", f"Argumento '{param_id}' debe ser de tipo {param_tipo}.", self.linea, self.columna)
                return ResultadoObtenido("None", "None")
            param_simbolo = Simbolo(param_id, param_tipo, arg_val.valor, True, entorno_local.nombre_ambito, self.linea, self.columna)
            entorno_local.guardar_variable(param_id, param_simbolo)

        try:
            simbolo_fn.bloque.ejecutar(entorno_local)
        except ReturnException as ret:
            if simbolo_fn.tipo_retorno and ret.resultado.tipo != simbolo_fn.tipo_retorno:
                entorno.registrar_error("Semántico", f"Tipo de retorno incorrecto en '{self.nombre}'.", self.linea, self.columna)
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
            if res is None or res.tipo == "None": return ResultadoObtenido("None", "None")
            if tipo_elem is None:
                tipo_elem = res.tipo
            elif tipo_elem != res.tipo:
                entorno.registrar_error("Semántico", "Tipos inconsistentes en arreglo.", self.linea, self.columna)
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

        if idx_res is None or idx_res.tipo != 'i32':
            entorno.registrar_error("Semántico", "El índice debe ser i32.", self.linea, self.columna)
            return ResultadoObtenido("None", "None")

        if not isinstance(arr_res.valor, list):
            entorno.registrar_error("Semántico", "La expresión no es un arreglo.", self.linea, self.columna)
            return ResultadoObtenido("None", "None")

        try:
            val = arr_res.valor[idx_res.valor]
            tipo_interno = arr_res.tipo.strip('[]')
            return ResultadoObtenido(val, tipo_interno)
        except IndexError:
            entorno.registrar_error("Semántico", f"Índice fuera de rango ({idx_res.valor}).", self.linea, self.columna)
            return ResultadoObtenido("None", "None")

class AsignacionArreglo(Instruccion):
    def __init__(self, identificador, indice, expresion, linea, columna):
        super().__init__(linea, columna)
        self.identificador = identificador
        self.indice = indice
        self.expresion = expresion

    def ejecutar(self, entorno):
        simbolo = entorno.obtener_variable(self.identificador)
        if not simbolo or not isinstance(simbolo.valor, list):
            entorno.registrar_error("Semántico", f"'{self.identificador}' no es un arreglo válido.", self.linea, self.columna)
            return

        idx_res = self.indice.ejecutar(entorno)
        val_res = self.expresion.ejecutar(entorno)
        if idx_res is None or val_res is None or idx_res.tipo != 'i32': return

        try:
            simbolo.valor[idx_res.valor] = val_res.valor
        except IndexError:
            entorno.registrar_error("Semántico", f"Índice fuera de rango ({idx_res.valor}).", self.linea, self.columna)

class DeclaracionStruct(Instruccion):
    def __init__(self, nombre, campos, linea, columna):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.campos = campos

    def ejecutar(self, entorno):
        entorno.guardar_variable(self.nombre, self.campos)

class InstanciacionStruct(Expresion):
    def __init__(self, nombre, campos_asignados, linea, columna):
        super().__init__(linea, columna)
        self.nombre = nombre
        self.campos_asignados = campos_asignados

    def ejecutar(self, entorno):
        struct_def = entorno.obtener_variable(self.nombre)
        if struct_def is None:
            entorno.registrar_error("Semántico", f"El struct '{self.nombre}' no existe.", self.linea, self.columna)
            return ResultadoObtenido("None", "None")

        campos_definidos = struct_def.valor if hasattr(struct_def, 'valor') else struct_def
        instancia_valores = {}
        for nombre_campo, expresion in self.campos_asignados.items():
            if nombre_campo in campos_definidos:
                instancia_valores[nombre_campo] = expresion.ejecutar(entorno)

        return ResultadoObtenido(instancia_valores, self.nombre)

class AccesoAtributo(Expresion):
    def __init__(self, expresion, atributo, linea, columna):
        super().__init__(linea, columna)
        self.expresion = expresion
        self.atributo = atributo

    def ejecutar(self, entorno):
        res_obj = self.expresion.ejecutar(entorno)
        if res_obj and isinstance(res_obj.valor, dict) and self.atributo in res_obj.valor:
            res_campo = res_obj.valor[self.atributo]
            return ResultadoObtenido(res_campo.valor, res_campo.tipo)
        
        entorno.registrar_error("Semántico", f"Atributo '{self.atributo}' inválido.", self.linea, self.columna)
        return ResultadoObtenido("None", "None")

class AsignacionAtributo(Instruccion):
    def __init__(self, identificador, atributo, expresion, linea, columna):
        super().__init__(linea, columna)
        self.identificador = identificador
        self.atributo = atributo
        self.expresion = expresion

    def ejecutar(self, entorno):
        simbolo = entorno.obtener_variable(self.identificador)
        if simbolo and isinstance(simbolo.valor, dict) and self.atributo in simbolo.valor:
            val_res = self.expresion.ejecutar(entorno)
            if val_res and val_res.tipo != "None":
                simbolo.valor[self.atributo] = val_res.valor

class MetodoLen(Expresion):
    def __init__(self, objeto, linea, columna):
        super().__init__(linea, columna)
        self.objeto = objeto

    def ejecutar(self, entorno):
        res_obj = self.objeto.ejecutar(entorno)
        if res_obj and isinstance(res_obj.valor, (str, list)):
            return ResultadoObtenido(len(res_obj.valor), "i32")
        return ResultadoObtenido(0, "i32")

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
        if val_match is None or val_match.tipo == "None":
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
                self.bloque.ejecutar(entorno)
            except BreakException as b:
                if b.etiqueta is None or b.etiqueta == self.etiqueta:
                    break
                else:
                    raise b
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
        if res_cant is None or res_cant.tipo != 'i32': return ResultadoObtenido("None", "None")
        return ResultadoObtenido([res_val.valor] * res_cant.valor, f"[{res_val.tipo}]")

class SliceArreglo(Expresion):
    def __init__(self, arreglo, inicio, fin, linea, columna):
        super().__init__(linea, columna)
        self.arreglo = arreglo
        self.inicio = inicio
        self.fin = fin

    def ejecutar(self, entorno):
        res_arr = self.arreglo.ejecutar(entorno)
        res_i = self.inicio.ejecutar(entorno)
        res_f = self.fin.ejecutar(entorno)
        if res_i and res_f and isinstance(res_arr.valor, list):
            return ResultadoObtenido(res_arr.valor[res_i.valor:res_f.valor], res_arr.tipo)
        return ResultadoObtenido("None", "None")

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
        val_args = [arg.ejecutar(entorno).valor for arg in self.argumentos if arg.ejecutar(entorno)]

        if res_obj and isinstance(res_obj.valor, str):
            if self.metodo == 'replace': return ResultadoObtenido(res_obj.valor.replace(str(val_args[0]), str(val_args[1])), "String")
            elif self.metodo == 'contains': return ResultadoObtenido(str(val_args[0]) in res_obj.valor, "bool")
            elif self.metodo == 'to_uppercase': return ResultadoObtenido(res_obj.valor.upper(), "String")
            elif self.metodo == 'to_lowercase': return ResultadoObtenido(res_obj.valor.lower(), "String")
            elif self.metodo == 'split': return ResultadoObtenido(res_obj.valor.split(str(val_args[0])), "[String]")
            elif self.metodo == 'split_whitespace': return ResultadoObtenido(res_obj.valor.split(), "[String]")

        elif res_obj and isinstance(res_obj.valor, list):
            if self.metodo == 'contains': return ResultadoObtenido(val_args[0] in res_obj.valor, "bool")
            elif self.metodo == 'reverse':
                res_obj.valor.reverse()
                return ResultadoObtenido(res_obj.valor, res_obj.tipo)
            elif self.metodo == 'collect': return ResultadoObtenido(res_obj.valor, res_obj.tipo)

        return ResultadoObtenido("None", "None")