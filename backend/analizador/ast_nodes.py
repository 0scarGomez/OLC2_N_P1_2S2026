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
        self.izq = izq  # Nodo expresión izquierdo
        self.der = der  # Nodo expresión derecho

    def ejecutar(self, entorno):
        izq = self.izq.ejecutar(entorno)
        der = self.der.ejecutar(entorno)

        if self.operador == '+':
            # Validación semántica según la tabla de tipos
            if izq.tipo == 'i32' and der.tipo == 'i32':
                return ResultadoObtenido(izq.valor + der.valor, 'i32')
            elif izq.tipo == 'f64' and der.tipo == 'f64':
                return ResultadoObtenido(izq.valor + der.valor, 'f64')
            else:
                # Generamos el Error Semántico si los tipos no son compatibles
                mensaje = f"No es posible aplicar el operador '+' entre los tipos {izq.tipo} y {der.tipo}."
                print(f"[Error Semántico] Línea {self.linea}, Columna {self.columna}\n{mensaje}")
                # Resiliencia
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