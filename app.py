import io
import sys
import subprocess
from flask import Flask, render_template, request, jsonify
from backend.analizador.lexer import lexer, errores_lexicos
from backend.analizador.parser import parser, errores_sintacticos

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

        def guardar_variable(self, nombre, simbolo):
            self.tabla[nombre] = simbolo
            self.todos_los_simbolos.append(simbolo)

        def obtener_variable(self, nombre):
            if nombre in self.tabla:
                return self.tabla[nombre]
            if self.anterior:
                return self.anterior.obtener_variable(nombre)
            return None

        def actualizar_variable(self, nombre, valor):
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

def generar_reporte_simbolos_html(simbolos):
    html = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Reporte de Tabla de Símbolos</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            h2 { color: #333; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 14px; }
            th, td { border: 1px solid black; padding: 10px; text-align: left; }
            th { background-color: #2563eb; color: white; font-weight: bold; }
            tr:nth-child(even) { background-color: #f8fafc; }
        </style>
    </head>
    <body>
        <h2>Organización de Lenguajes y Compiladores 2</h2>
        <h3>Reporte Tabla de Símbolos</h3>
        <table>
            <thead>
                <tr>
                    <th>No.</th>
                    <th>Identificador</th>
                    <th>Categoría</th>
                    <th>Tipo</th>
                    <th>Ámbito</th>
                    <th>Línea</th>
                    <th>Valor</th>
                </tr>
            </thead>
            <tbody>
    """
    for i, sim in enumerate(simbolos, 1):
        html += f"""
                <tr>
                    <td>{i}</td>
                    <td>{sim.get('id', '')}</td>
                    <td>{sim.get('categoria', '')}</td>
                    <td>{sim.get('tipo', '')}</td>
                    <td>{sim.get('ambito', '')}</td>
                    <td>{sim.get('linea', '')}</td>
                    <td>{sim.get('valor', '')}</td>
                </tr>
        """
    html += """
            </tbody>
        </table>
    </body>
    </html>
    """
    try:
        with open("reporte_simbolos.html", "w", encoding="utf-8") as f:
            f.write(html)
    except Exception as e:
        print(f"No se pudo generar el reporte HTML: {e}")

# --- GENERACIÓN Y COMPILACIÓN DEL ARBOL AST ---
def guardar_reporte_ast(dot_string):
    svg_content = ""
    try:
        # Save source DOT file
        with open("reporte_ast.dot", "w", encoding="utf-8") as f:
            f.write(dot_string)
        
        # Compile PNG, PDF, and SVG files using Graphviz dot CLI
        subprocess.run(["dot", "-Tpng", "reporte_ast.dot", "-o", "reporte_ast.png"], check=True)
        subprocess.run(["dot", "-Tpdf", "reporte_ast.dot", "-o", "reporte_ast.pdf"], check=True)
        subprocess.run(["dot", "-Tsvg", "reporte_ast.dot", "-o", "reporte_ast.svg"], check=True)
        
        # Read compiled SVG content to render directly on the web page
        with open("reporte_ast.svg", "r", encoding="utf-8") as f:
            svg_content = f.read()

        print("Reportes AST (DOT, PNG, PDF, SVG) generados exitosamente.")
    except FileNotFoundError:
        print("Aviso: Se generó 'reporte_ast.dot', pero 'dot' (Graphviz) no está en el PATH del sistema.")
    except Exception as e:
        print(f"Error al generar las imágenes del AST: {e}")
    return svg_content

def generar_dot_ast(ast):
    if not ast:
        return 'digraph AST { "Sin Nodos" };'
    
    dot = ['digraph AST {', 'node [shape=box, style=solid, fontname="Arial"];']
    dot.append('root [label="Program"];')
    
    contador = [1]
    
    def recorrer(nodo, padre_id):
        if nodo is None:
            return
        
        node_id = f"node_{contador[0]}"
        contador[0] += 1
        
        nombre_clase = nodo.__class__.__name__
        label = nombre_clase
        
        if hasattr(nodo, 'id') and getattr(nodo, 'id'): 
            label = f"{nombre_clase}\\n{nodo.id}"
        elif hasattr(nodo, 'operador') and getattr(nodo, 'operador'): 
            label = f"{nombre_clase}\\n{nodo.operador}"
        elif hasattr(nodo, 'valor') and getattr(nodo, 'valor') is not None: 
            label = f"{nombre_clase}\\n{nodo.valor}"

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

    errores_lexicos.clear()
    errores_sintacticos.clear()

    old_stdout = sys.stdout
    sys.stdout = buffer_salida = io.StringIO()

    simbolos_lista = []

    try:
        lexer.lineno = 1
        ast = parser.parse(codigo, lexer=lexer)
        salida_parseo = buffer_salida.getvalue()

        if ast is not None:
            entorno_global = Entorno(nombre_ambito="Global")
            buffer_salida.truncate(0)
            buffer_salida.seek(0)

            # Ejecución de sentencias globales
            for instruccion in ast:
                if instruccion is not None:
                    instruccion.ejecutar(entorno_global)

            # Ejecutar main() automáticamente
            simbolo_main = entorno_global.obtener_variable('main')
            if simbolo_main and getattr(simbolo_main, 'tipo', None) == 'Funcion':
                from backend.analizador.ast_nodes import LlamadaFuncion
                llamada_main = LlamadaFuncion('main', [], 1, 1)
                llamada_main.ejecutar(entorno_global)

            salida_ejecucion = buffer_salida.getvalue()

            # Recolectar lista global de símbolos
            if hasattr(entorno_global, 'todos_los_simbolos'):
                for sim in entorno_global.todos_los_simbolos:
                    nombre = getattr(sim, 'identificador', 'Desconocido')
                    tipo_str = str(getattr(sim, 'tipo', 'Desconocido'))
                    valor_bruto = getattr(sim, 'valor', '—')
                    ambito = getattr(sim, 'ambito', 'Global')
                    linea = getattr(sim, 'linea', '-')
                    
                    categoria = 'Variable'
                    valor = str(valor_bruto)
                    
                    if tipo_str.lower() in ['funcion', 'función']:
                        categoria = 'Función'
                        valor = '—'
                    elif tipo_str.lower() in ['struct', 'modulo']:
                        categoria = 'Struct'
                        valor = '—'
                        
                    simbolos_lista.append({
                        'id': nombre,
                        'categoria': categoria,
                        'tipo': tipo_str,
                        'ambito': str(ambito),
                        'linea': str(linea),
                        'valor': valor
                    })
            
            # Generar Reporte HTML de Símbolos
            generar_reporte_simbolos_html(simbolos_lista)

            # Generar Reportes de AST (Archivos físicos .dot, .png, .pdf y string SVG)
            cadena_dot_ast = generar_dot_ast(ast)
            svg_ast = guardar_reporte_ast(cadena_dot_ast)

            todos_los_errores = errores_lexicos + errores_sintacticos + entorno_global.errores

            return jsonify({
                'exito': True if len(todos_los_errores) == 0 else False,
                'consola': salida_ejecucion if salida_ejecucion else "=== EJECUCIÓN EXITOSA SIN IMPRESIONES ===",
                'simbolos': simbolos_lista,
                'errores': todos_los_errores,
                'ast_dot': cadena_dot_ast,
                'ast_svg': svg_ast
            })
        else:
            salida_consola = buffer_salida.getvalue() or salida_parseo
            return jsonify({
                'exito': False,
                'consola': salida_consola or '[Error Léxico/Sintáctico] No se pudo parsear el código.',
                'simbolos': [],
                'errores': errores_lexicos + errores_sintacticos,
                'ast_dot': 'digraph AST { "Error en Análisis" };',
                'ast_svg': ''
            })

    except Exception as e:
        return jsonify({
            'exito': False,
            'consola': f"[Error de Ejecución]: {str(e)}",
            'simbolos': [],
            'errores': errores_lexicos + errores_sintacticos + [{'tipo': 'Excepción de Python', 'descripcion': str(e), 'linea': '-', 'columna': '-'}],
            'ast_dot': 'digraph AST { "Error de Ejecución" };',
            'ast_svg': ''
        })
    finally:
        sys.stdout = old_stdout

if __name__ == '__main__':
    app.run(debug=True, port=5000)