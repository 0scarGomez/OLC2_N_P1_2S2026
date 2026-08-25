class Simbolo:
    def __init__(self, identificador, tipo, valor, es_mutable, ambito, linea, columna):
        self.identificador = identificador
        self.tipo = tipo
        self.valor = valor
        self.es_mutable = es_mutable # Para verificar errores al reasignar
        self.ambito = ambito         
        self.linea = linea
        self.columna = columna

class Entorno:
    def __init__(self, anterior=None, nombre_ambito="Global"):
        self.tabla = {}          # Diccionario de identificador 
        self.anterior = anterior # Entorno padre
        self.nombre_ambito = nombre_ambito

    def guardar_variable(self, identificador, simbolo):
        self.tabla[identificador] = simbolo

    def obtener_variable(self, identificador):
        entorno_actual = self
        while entorno_actual is not None:
            if identificador in entorno_actual.tabla:
                return entorno_actual.tabla[identificador]
            entorno_actual = entorno_actual.anterior
        return None # Generara un Error Semantico 

    def actualizar_variable(self, identificador, nuevo_valor):
        entorno_actual = self
        while entorno_actual is not None:
            if identificador in entorno_actual.tabla:
                simbolo = entorno_actual.tabla[identificador]
                if not simbolo.es_mutable:
                    return "ERROR_INMUTABLE" # La variable es inmutable por defecto
                simbolo.valor = nuevo_valor
                return "OK"
            entorno_actual = entorno_actual.anterior
        return "ERROR_NO_ENCONTRADA"