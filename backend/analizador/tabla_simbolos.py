class Simbolo:
    def __init__(self, identificador, tipo, valor, es_mutable, ambito, linea, columna):
        self.identificador = identificador
        self.tipo = tipo
        self.valor = valor
        self.es_mutable = es_mutable 
        self.ambito = ambito         
        self.linea = linea
        self.columna = columna

class Entorno:
    def __init__(self, anterior=None, nombre_ambito="Global"):
        self.tabla = {}          
        self.anterior = anterior 
        self.nombre_ambito = nombre_ambito
        self.errores = anterior.errores if anterior else []
        self.todos_los_simbolos = anterior.todos_los_simbolos if anterior else []

    def registrar_error(self, tipo, descripcion, linea, columna):
        self.errores.append({
            'tipo': tipo,
            'descripcion': descripcion,
            'linea': linea,
            'columna': columna
        })
        print(f"[{tipo}] Línea {linea}, Columna {columna}\n{descripcion}")

    def guardar_variable(self, identificador, simbolo):
        self.tabla[identificador] = simbolo
        self.todos_los_simbolos.append(simbolo)

    def obtener_variable(self, identificador):
        entorno_actual = self
        while entorno_actual is not None:
            if identificador in entorno_actual.tabla:
                return entorno_actual.tabla[identificador]
            entorno_actual = entorno_actual.anterior
        return None 

    def actualizar_variable(self, identificador, nuevo_valor):
        entorno_actual = self
        while entorno_actual is not None:
            if identificador in entorno_actual.tabla:
                simbolo = entorno_actual.tabla[identificador]
                if not getattr(simbolo, 'es_mutable', False):
                    return "ERROR_INMUTABLE" 
                simbolo.valor = nuevo_valor
                return "OK"
            entorno_actual = entorno_actual.anterior
        return "ERROR_NO_ENCONTRADA"