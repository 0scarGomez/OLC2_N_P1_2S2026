from backend.analizador.lexer import lexer
from backend.analizador.parser  import parser
from backend.analizador.tabla_simbolos import Entorno

codigo_prueba = """
let mut x: i32 = 10 + 5;
let y: String = 20; 
"""

def probar_interprete():
    print("=== INICIANDO COMPILACIÓN Y EJECUCIÓN ===")
    
   
    ast = parser.parse(codigo_prueba, lexer=lexer)
    
    entorno_global = Entorno(nombre_ambito="Global")
    
    if ast:
        print("\n--- Analizando Semántica ---")
        for instruccion in ast:
            if instruccion: # Evitamos Nones de posibles errores previos
                instruccion.ejecutar(entorno_global)
    
    print("\n=== TABLA DE SIMBOLOS FINAL ===")
    if not entorno_global.tabla:
        print("La tabla de simbolos esta vacia.")
    else:
        for identificador, simbolo in entorno_global.tabla.items():
            print(f"Variable: {identificador} | Tipo: {simbolo.tipo} | Valor: {simbolo.valor} | Mutable: {simbolo.es_mutable}")

if __name__ == '__main__':
    probar_interprete()