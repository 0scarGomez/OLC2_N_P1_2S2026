# OxigenNative — OLC2 Proyecto 2 

Compilador de **OxigenNative** (lenguaje de sintaxis estática inspirada en Rust) escrito en **Python + PLY**, con GUI en **Django**. Traduce el AST directamente a **ARM64**, lo ensambla/enlaza y lo ejecuta con **QEMU User Mode**.

```bash
sudo apt install binutils-aarch64-linux-gnu qemu-user graphviz
pip install -r requirements.txt
python3 manage.py runserver          # http://127.0.0.1:8000
```

* Documentación técnica: [`docs/DOCUMENTACION_TECNICA.md`](docs/DOCUMENTACION_TECNICA.md)
* Manual de usuario: [`docs/MANUAL_USUARIO.md`](docs/MANUAL_USUARIO.md)
