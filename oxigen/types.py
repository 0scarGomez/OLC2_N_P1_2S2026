"""Sistema de tipos estáticos de OxigenNative."""


class Type:
    name = "?"

    def __repr__(self):
        return self.name

    def __eq__(self, other):
        return isinstance(other, Type) and repr(self) == repr(other)

    def __hash__(self):
        return hash(repr(self))


class Prim(Type):
    def __init__(self, name):
        self.name = name


class ArrayType(Type):
    """Arreglo de tamaño fijo [T; N]. `slice=True` marca una vista (&arr[a..b])."""

    def __init__(self, elem, size, slice_=False):
        self.elem = elem
        self.size = size
        self.slice = slice_

    @property
    def name(self):
        return f"[{self.elem}; {self.size}]"

    def display(self):
        """Nombre que muestra typeof()."""
        if self.slice:
            return f"&[{self.elem.display() if isinstance(self.elem, ArrayType) else self.elem}]"
        return f"[{self.elem.display() if isinstance(self.elem, ArrayType) else self.elem}; {self.size}]"


class VecType(Type):
    """Arreglo dinámico (resultado de split / split_whitespace)."""

    def __init__(self, elem):
        self.elem = elem

    @property
    def name(self):
        return f"Vec<{self.elem}>"


I32 = Prim("i32")
F64 = Prim("f64")
BOOL = Prim("bool")
CHAR = Prim("char")
STRING = Prim("String")
UNIT = Prim("()")
NONE = Prim("None")   # tipo del resultado de una expresión inválida


def display(t):
    return t.display() if isinstance(t, ArrayType) else repr(t)


def words(t):
    """Cantidad de palabras de 8 bytes que ocupa un valor de tipo t dentro de un arreglo plano."""
    if isinstance(t, ArrayType):
        return t.size * words(t.elem)
    return 1


def base_elem(t):
    while isinstance(t, ArrayType):
        t = t.elem
    return t


def is_numeric(t):
    return t in (I32, F64)


def is_pointer(t):
    return t == STRING or isinstance(t, (ArrayType, VecType))


def is_float(t):
    return t == F64


def default_value_kind(t):
    """Devuelve 'zero' | 'empty' | None (sin valor por defecto)."""
    if t in (I32, F64, BOOL):
        return "zero"
    if t == STRING:
        return "empty"
    return None
