"""Sistema de tipos estático"""

class Type:
    __slots__ = ("kind", "elem", "n")

    def __init__(self, kind, elem=None, n=None):
        self.kind = kind
        self.elem = elem
        self.n = n

    # ------------------------------------------------------------------
    def __eq__(self, other):
        return (
            isinstance(other, Type)
            and self.kind == other.kind
            and self.elem == other.elem
            and self.n == other.n
        )

    def __hash__(self):
        return hash((self.kind, self.elem, self.n))

    def __str__(self):
        k = self.kind
        if k == "struct":
            return self.n
        if k == "array":
            return f"[{self.elem}; {self.n}]"
        if k == "slice":
            return f"&[{self.elem}]"
        if k == "vec":
            inner = "&str" if self.elem.kind == "String" else str(self.elem)
            return f"Vec<{inner}>"
        if k == "unit":
            return "()"
        return k

    __repr__ = __str__

    # ------------------------------------------------------------------
    @property
    def is_numeric(self):
        return self.kind in ("i32", "f64")

    @property
    def is_seq(self):
        return self.kind in ("array", "slice", "vec")

    @property
    def is_none(self):
        return self.kind == "none"

    @property
    def is_float(self):
        return self.kind == "f64"

    @property
    def is_aggregate(self):
        """Arreglos y structs se almacenan contiguos; su valor es un puntero."""
        return self.kind in ("array", "slice", "vec", "struct")

    @property
    def is_struct(self):
        return self.kind == "struct"

    def slots(self):
        """Cantidad de celdas de 8 bytes que ocupa el valor dentro de un arreglo/struct."""
        if self.kind == "array":
            return self.n * self.elem.slots()
        if self.kind == "struct":
            return sum(t.slots() for _, t in STRUCTS.get(self.n, [])) or 1
        return 1

    def field_offset(self, name):
        """(offset en bytes, tipo) del campo `name` de un struct, o None."""
        off = 0
        for fname, ft in STRUCTS.get(self.n, []):
            if fname == name:
                return off, ft
            off += ft.slots() * 8
        return None

    def byte_size(self):
        return self.slots() * 8

    def depth(self):
        d = 0
        t = self
        while t.is_seq:
            d += 1
            t = t.elem
        return d


# registro de structs de la compilación actual: nombre -> [(campo, Type)]
STRUCTS = {}


def struct_of(name):
    return Type("struct", None, name)


I32 = Type("i32")
F64 = Type("f64")
BOOL = Type("bool")
CHAR = Type("char")
STRING = Type("String")
UNIT = Type("unit")
NONE = Type("none")


def array_of(elem, n):
    return Type("array", elem, n)


def slice_of(elem, n):
    return Type("slice", elem, n)


def vec_of(elem):
    return Type("vec", elem)


def default_value(t):
    if t.kind == "struct":
        return None
    """Valor por defecto textual (para la tabla de símbolos) o None si no existe."""
    return {"i32": "0", "f64": "0.0", "bool": "false", "String": '""', "char": "'\\0'"}.get(t.kind)


def assignable(dst, src):
    """¿Se puede asignar un valor de tipo `src` a un destino de tipo `dst`?"""
    if dst.is_none or src.is_none:
        return True
    if dst == src:
        return True
    if dst.kind == "f64" and src.kind == "i32":  # promoción numérica
        return True
    if dst.kind in ("array", "slice", "vec") and src.kind in ("array", "slice", "vec"):
        # una vista/arreglo es compatible con otro del mismo tipo de elemento
        if dst.kind == "array" and src.kind != "array":
            return False
        if dst.elem == src.elem:
            if dst.kind == "array":
                return dst.n == src.n
            if dst.kind == "slice":
                return src.kind in ("array", "slice") and (dst.n == src.n)
            return dst.kind == "vec" and src.kind == "vec"
    return False
