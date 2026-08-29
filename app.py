import io
import sys
from flask import Flask, render_template, request, jsonify
from backend.analizador.lexer import lexer, errores_lexicos
from backend.analizador.parser import parser

# Búsqueda flexible de la clase Entorno
Entorno = None
posibles_modulos = [
    'backend.analizador.entorno',
    'backend.analizador.tabla_simbolos',
    'backend.analizador.ast_nodes',
    'backend.analizador.environment'
]

for modulo in posibles_modulos:
    try:
        m = __import__(modulo, fromlist=['Entorno'])
        if hasattr(m, 'Entorno'):
            Entorno = getattr(m, 'Entorno')
            break
    except ModuleNotFoundError:
        continue

if Entorno is None:
    class Entorno:
        def __init__(self, anterior=None, nombre_ambito="Global"):
            self.tabla = {}
            self.anterior = anterior
            self.nombre_ambito = nombre_ambito

        def guardar_variable(self, nombre, simbolo):
            # El Sombreado (Shadowing) ocurre aquí. Al usar 'let', simplemente 
            # sobrescribimos la llave en el diccionario del entorno actual, 
            # sin importar si era inmutable o de otro tipo.
            self.tabla[nombre] = simbolo

        def obtener_variable(self, nombre):
            if nombre in self.tabla:
                return self.tabla[nombre]
            if self.anterior:
                return self.anterior.obtener_variable(nombre)
            return None

        def actualizar_variable(self, nombre, valor):
            # La Asignación normal ocurre aquí (sin 'let'). Verificamos mutabilidad.
            if nombre in self.tabla:
                simbolo = self.tabla[nombre]
                es_mut = getattr(simbolo, 'es_mutable', getattr(simbolo, 'mutable', False))
                
                if not es_mut:
                    return "ERROR_INMUTABLE"
                
                simbolo.valor = valor
                return "OK"
                
            if self.anterior:
                return self.anterior.actualizar_variable(nombre, valor)
            return None

app = Flask(__name__)

def generar_dot_ast(ast):
    if not ast:
        return 'digraph AST { "Sin Nodos" };'
    
    dot = ['digraph AST {', 'node [shape=box, style=filled, fillcolor="#e0f2fe", fontname="Consolas"];']
    dot.append('root [label="RAÍZ (Raiz)"];')
    
    contador = [1]
    
    def recorrer(nodo, padre_id):
        if nodo is None:
            return
        
        node_id = f"node_{contador[0]}"
        contador[0] += 1
        
        nombre_clase = nodo.__class__.__name__
        label = nombre_clase
        
        if hasattr(nodo, 'id') and getattr(nodo, 'id'): 
            label += f'\\n({nodo.id})'
        elif hasattr(nodo, 'operador') and getattr(nodo, 'operador'): 
            label += f'\\n({nodo.operador})'
        elif hasattr(nodo, 'valor') and getattr(nodo, 'valor') is not None: 
            label += f'\\n({nodo.valor})'

        dot.append(f'{node_id} [label="{label}"];')
        dot.append(f'{padre_id} -> {node_id};')

        for attr in vars(nodo):
            val = getattr(nodo, attr)
            if isinstance(val, list):
                for item in val:
                    if hasattr(item, '__class__') and hasattr(item, '__dict__'):
                        recorrer(item, node_id)
            elif hasattr(val, '__class__') and hasattr(val, '__dict__'):
                recorrer(val, node_id)

    for inst in ast:
        if inst is not None:
            recorrer(inst, "root")
            
    dot.append('}')
    return '\n'.join(dot)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ejecutar', methods=['POST'])
def ejecutar():
    datos = request.get_json()
    codigo = datos.get('codigo', '')

    # Limpiar lista de errores léxicos previos
    errores_lexicos.clear()

    old_stdout = sys.stdout
    sys.stdout = buffer_salida = io.StringIO()

    errores_lista = []
    simbolos_lista = []

    try:
        # Reiniciar número de línea del lexer para cada ejecución
        lexer.lineno = 1
        ast = parser.parse(codigo, lexer=lexer)
        salida_parseo = buffer_salida.getvalue()

        if ast is not None and len(errores_lexicos) == 0:
            entorno_global = Entorno()
            buffer_salida.truncate(0)
            buffer_salida.seek(0)

            # 1. Registrar declaraciones globales
            for instruccion in ast:
                if instruccion is not None:
                    instruccion.ejecutar(entorno_global)

            # 2. Ejecutar función main() automáticamente
            simbolo_main = None
            if hasattr(entorno_global, 'obtener_variable'):
                simbolo_main = entorno_global.obtener_variable('main')
            elif hasattr(entorno_global, 'tabla'):
                simbolo_main = entorno_global.tabla.get('main')

            if simbolo_main and getattr(simbolo_main, 'tipo', None) == 'Funcion':
                from backend.analizador.ast_nodes import LlamadaFuncion
                llamada_main = LlamadaFuncion('main', [], 1, 1)
                llamada_main.ejecutar(entorno_global)

            salida_ejecucion = buffer_salida.getvalue()

            if hasattr(entorno_global, 'tabla'):
                for nombre, sim in entorno_global.tabla.items():
                    tipo = getattr(sim, 'tipo', 'Desconocido')
                    valor = getattr(sim, 'valor', getattr(sim, 'value', str(sim)))
                    mutable = getattr(sim, 'es_mutable', getattr(sim, 'mutable', False))
                    simbolos_lista.append({
                        'id': nombre,
                        'tipo': str(tipo),
                        'valor': str(valor),
                        'mutable': 'Sí' if mutable else 'No'
                    })

            return jsonify({
                'exito': True,
                'consola': salida_ejecucion if salida_ejecucion else "=== EJECUCIÓN EXITOSA SIN IMPRESIONES ===",
                'simbolos': simbolos_lista,
                'errores': errores_lista + errores_lexicos,
                'ast_dot': generar_dot_ast(ast)
            })
        else:
            salida_consola = buffer_salida.getvalue() or salida_parseo
            return jsonify({
                'exito': False,
                'consola': salida_consola or '[Error Léxico/Sintáctico] No se pudo parsear el código.',
                'simbolos': [],
                'errores': errores_lexicos if errores_lexicos else [{'tipo': 'Sintáctico', 'descripcion': 'Error en la estructura sintáctica del código', 'linea': 1, 'columna': 1}],
                'ast_dot': 'digraph AST { "Error en Análisis" };'
            })

    except Exception as e:
        return jsonify({
            'exito': False,
            'consola': f"[Error de Ejecución]: {str(e)}",
            'simbolos': [],
            'errores': errores_lexicos + [{'tipo': 'Semántico', 'descripcion': str(e), 'linea': '-', 'columna': '-'}],
            'ast_dot': 'digraph AST { "Error de Ejecución" };'
        })
    finally:
        sys.stdout = old_stdout

if __name__ == '__main__':
    app.run(debug=True, port=5000)