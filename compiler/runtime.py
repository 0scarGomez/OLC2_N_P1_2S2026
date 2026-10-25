"""Runtime ARM64 que acompaña a todo programa generado"""

ROUTINES = {}
DEPS = {}


def routine(name, deps, text):
    ROUTINES[name] = text.strip("\n") + "\n"
    DEPS[name] = deps


# ---------------------------------------------------------------------------
# Entrada / salida con buffer
# ---------------------------------------------------------------------------
routine("_flush", [], r"""
# _flush: escribe el buffer de salida en stdout (fd 1)
_flush:
    adrp x9, _outpos
    ldr  x2, [x9, :lo12:_outpos]
    cbz  x2, .Lfl_done
    adrp x1, _outbuf
    add  x1, x1, :lo12:_outbuf
.Lfl_loop:
    mov  x0, #1
    mov  x8, #64                 // sys_write
    svc  #0
    cmp  x0, #0
    b.le .Lfl_done
    add  x1, x1, x0
    sub  x2, x2, x0
    cbnz x2, .Lfl_loop
.Lfl_done:
    str  xzr, [x9, :lo12:_outpos]
    ret
""")

routine("_out_write", ["_flush"], r"""
# _out_write(x0 = ptr, x1 = longitud): copia bytes al buffer de salida
_out_write:
    stp  x29, x30, [sp, #-16]!
    mov  x29, sp
.Low_loop:
    cbz  x1, .Low_done
    adrp x9, _outpos
    ldr  x11, [x9, :lo12:_outpos]
    mov  x12, #65536
    cmp  x11, x12
    b.lo .Low_room
    stp  x0, x1, [sp, #-16]!
    bl   _flush
    ldp  x0, x1, [sp], #16
    b    .Low_loop
.Low_room:
    adrp x10, _outbuf
    add  x10, x10, :lo12:_outbuf
    ldrb w12, [x0], #1
    strb w12, [x10, x11]
    add  x11, x11, #1
    str  x11, [x9, :lo12:_outpos]
    sub  x1, x1, #1
    b    .Low_loop
.Low_done:
    ldp  x29, x30, [sp], #16
    ret
""")

routine("_strlen", [], r"""
# _strlen(x0 = cadena) -> x0 = bytes hasta el NUL
_strlen:
    mov  x1, x0
.Lsl_loop:
    ldrb w2, [x1], #1
    cbnz w2, .Lsl_loop
    sub  x0, x1, x0
    sub  x0, x0, #1
    ret
""")

routine("_print_str", ["_strlen", "_out_write"], r"""
# _print_str(x0 = cadena)
_print_str:
    stp  x29, x30, [sp, #-16]!
    mov  x29, sp
    mov  x9, x0
    bl   _strlen
    mov  x1, x0
    mov  x0, x9
    bl   _out_write
    ldp  x29, x30, [sp], #16
    ret
""")

routine("_print_qstr", ["_print_str", "_out_byte"], r"""
# _print_qstr(x0 = cadena): imprime entre comillas dobles (formato Debug)
_print_qstr:
    stp  x29, x30, [sp, #-32]!
    mov  x29, sp
    str  x19, [sp, #16]
    mov  x19, x0
    mov  w0, #34
    bl   _out_byte
    mov  x0, x19
    bl   _print_str
    mov  w0, #34
    bl   _out_byte
    ldr  x19, [sp, #16]
    ldp  x29, x30, [sp], #32
    ret
""")

routine("_out_byte", ["_out_write"], r"""
# _out_byte(w0 = byte)
_out_byte:
    stp  x29, x30, [sp, #-32]!
    mov  x29, sp
    strb w0, [sp, #16]
    add  x0, sp, #16
    mov  x1, #1
    bl   _out_write
    ldp  x29, x30, [sp], #32
    ret
""")

routine("_print_nl", ["_out_byte"], r"""
_print_nl:
    stp  x29, x30, [sp, #-16]!
    mov  x29, sp
    mov  w0, #10
    bl   _out_byte
    ldp  x29, x30, [sp], #16
    ret
""")

routine("_fmt_u64", [], r"""
# _fmt_u64(x0 = valor sin signo, x1 = fin del buffer) -> x0 = inicio de los dígitos
_fmt_u64:
    mov  x10, #10
.Lfu_loop:
    udiv x11, x0, x10
    msub x12, x11, x10, x0
    add  w12, w12, #48
    sub  x1, x1, #1
    strb w12, [x1]
    mov  x0, x11
    cbnz x0, .Lfu_loop
    mov  x0, x1
    ret
""")

routine("_print_int", ["_fmt_u64", "_out_write"], r"""
# _print_int(x0 = entero con signo)
_print_int:
    stp  x29, x30, [sp, #-64]!
    mov  x29, sp
    add  x1, sp, #64
    mov  x13, #0
    cmp  x0, #0
    b.ge .Lpi_pos
    neg  x0, x0
    mov  x13, #1
.Lpi_pos:
    str  x13, [sp, #16]
    add  x1, sp, #64
    bl   _fmt_u64
    ldr  x13, [sp, #16]
    cbz  x13, .Lpi_out
    sub  x0, x0, #1
    mov  w12, #45
    strb w12, [x0]
.Lpi_out:
    add  x1, sp, #64
    sub  x1, x1, x0
    bl   _out_write
    ldp  x29, x30, [sp], #64
    ret
""")

routine("_print_bool", ["_out_write"], r"""
# _print_bool(x0 = 0/1)
_print_bool:
    stp  x29, x30, [sp, #-16]!
    mov  x29, sp
    cbz  x0, .Lpb_f
    adrp x0, _s_true
    add  x0, x0, :lo12:_s_true
    mov  x1, #4
    b    .Lpb_w
.Lpb_f:
    adrp x0, _s_false
    add  x0, x0, :lo12:_s_false
    mov  x1, #5
.Lpb_w:
    bl   _out_write
    ldp  x29, x30, [sp], #16
    ret
""")

routine("_print_char", ["_out_write"], r"""
# _print_char(x0 = punto de código Unicode) -> escribe en UTF-8
_print_char:
    stp  x29, x30, [sp, #-32]!
    mov  x29, sp
    add  x9, sp, #16
    cmp  x0, #0x80
    b.hs .Lpc_2
    strb w0, [x9]
    mov  x1, #1
    b    .Lpc_w
.Lpc_2:
    cmp  x0, #0x800
    b.hs .Lpc_3
    lsr  x10, x0, #6
    orr  w10, w10, #0xC0
    strb w10, [x9]
    and  w10, w0, #0x3F
    orr  w10, w10, #0x80
    strb w10, [x9, #1]
    mov  x1, #2
    b    .Lpc_w
.Lpc_3:
    mov  x11, #0x10000
    cmp  x0, x11
    b.hs .Lpc_4
    lsr  x10, x0, #12
    orr  w10, w10, #0xE0
    strb w10, [x9]
    lsr  x10, x0, #6
    and  w10, w10, #0x3F
    orr  w10, w10, #0x80
    strb w10, [x9, #1]
    and  w10, w0, #0x3F
    orr  w10, w10, #0x80
    strb w10, [x9, #2]
    mov  x1, #3
    b    .Lpc_w
.Lpc_4:
    lsr  x10, x0, #18
    orr  w10, w10, #0xF0
    strb w10, [x9]
    lsr  x10, x0, #12
    and  w10, w10, #0x3F
    orr  w10, w10, #0x80
    strb w10, [x9, #1]
    lsr  x10, x0, #6
    and  w10, w10, #0x3F
    orr  w10, w10, #0x80
    strb w10, [x9, #2]
    and  w10, w0, #0x3F
    orr  w10, w10, #0x80
    strb w10, [x9, #3]
    mov  x1, #4
.Lpc_w:
    mov  x0, x9
    bl   _out_write
    ldp  x29, x30, [sp], #32
    ret
""")

routine("_print_qchar", ["_print_char", "_out_byte"], r"""
# _print_qchar(x0 = carácter): entre comillas simples (formato Debug)
_print_qchar:
    stp  x29, x30, [sp, #-32]!
    mov  x29, sp
    str  x19, [sp, #16]
    mov  x19, x0
    mov  w0, #39
    bl   _out_byte
    mov  x0, x19
    bl   _print_char
    mov  w0, #39
    bl   _out_byte
    ldr  x19, [sp, #16]
    ldp  x29, x30, [sp], #32
    ret
""")

# Impresión de f64: imprime la representación decimal más corta que vuelve a
# dar exactamente el mismo número (como Display de Rust); enteros llevan ".0".
routine("_print_f64", ["_fmt_u64", "_out_write", "_out_byte"], r"""
# _print_f64(d0 = valor)
_print_f64:
    stp  x29, x30, [sp, #-128]!
    mov  x29, sp
    fcmp d0, d0
    b.vc .Lpf_notnan
    adrp x0, _s_nan
    add  x0, x0, :lo12:_s_nan
    mov  x1, #3
    bl   _out_write
    b    .Lpf_ret
.Lpf_notnan:
    fmov x9, d0
    lsr  x10, x9, #63
    cbz  x10, .Lpf_abs
    str  d0, [sp, #16]
    mov  w0, #45
    bl   _out_byte
    ldr  d0, [sp, #16]
    fabs d0, d0
.Lpf_abs:
    fmov x9, d0
    movz x10, #0x7ff0, lsl #48
    cmp  x9, x10
    b.ne .Lpf_finite
    adrp x0, _s_inf
    add  x0, x0, :lo12:_s_inf
    mov  x1, #3
    bl   _out_write
    b    .Lpf_ret
.Lpf_finite:
    str  d0, [sp, #16]
    fcvtzu x11, d0               // parte entera (satura)
    ucvtf d1, x11
    fsub d2, d0, d1              // parte fraccionaria
    fcmp d2, #0.0
    b.ne .Lpf_frac
    // entero: "<n>.0"
    mov  x0, x11
    add  x1, sp, #128
    bl   _fmt_u64
    add  x1, sp, #128
    sub  x1, x1, x0
    bl   _out_write
    adrp x0, _s_dot0
    add  x0, x0, :lo12:_s_dot0
    mov  x1, #2
    bl   _out_write
    b    .Lpf_ret
.Lpf_frac:
    fmov d4, #1.0                // d4 = 10^n  (double)
    mov  x13, #1                 // x13 = 10^n (entero)
    fmov d5, #10.0
    mov  x14, #10
    mov  x15, #0                 // n
.Lpf_try:
    fmul d4, d4, d5
    mul  x13, x13, x14
    add  x15, x15, #1
    ldr  d0, [sp, #16]
    fmul d3, d0, d4              // x * 10^n
    movz x9, #0x43e0, lsl #48    // 2^63 como double
    fmov d6, x9
    fcmp d3, d6
    b.ge .Lpf_back               // overflow: usar n-1
    fcvtas x12, d3               // r = round(x*10^n)
    scvtf d7, x12
    fdiv d7, d7, d4              // r / 10^n
    fcmp d7, d0
    b.eq .Lpf_found
    cmp  x15, #17
    b.lo .Lpf_try
    b    .Lpf_found
.Lpf_back:
    // retrocede una cifra (n-1 siempre es válido porque n=1 no desborda)
    mov  x9, #10
    udiv x13, x13, x9
    sub  x15, x15, #1
    fmov d5, #10.0
    fdiv d4, d4, d5
    fmul d3, d0, d4
    fcvtas x12, d3
.Lpf_found:
    // x12 = r, x13 = 10^n, x15 = n
    udiv x0, x12, x13
    msub x16, x0, x13, x12       // x16 = fracción como entero
    str  x15, [sp, #24]
    str  x16, [sp, #32]
    add  x1, sp, #128
    bl   _fmt_u64
    add  x1, sp, #128
    sub  x1, x1, x0
    bl   _out_write
    mov  w0, #46
    bl   _out_byte
    // n dígitos con ceros a la izquierda
    ldr  x15, [sp, #24]
    ldr  x16, [sp, #32]
    add  x9, sp, #96             // buffer de dígitos [96, 96+n)
    add  x9, x9, x15
    mov  x10, x15
    mov  x11, #10
.Lpf_dig:
    udiv x12, x16, x11
    msub x13, x12, x11, x16
    add  w13, w13, #48
    sub  x9, x9, #1
    strb w13, [x9]
    mov  x16, x12
    subs x10, x10, #1
    b.ne .Lpf_dig
    mov  x0, x9
    mov  x1, x15
    bl   _out_write
.Lpf_ret:
    ldp  x29, x30, [sp], #128
    ret
""")


routine("_print_f64p", ["_fmt_u64", "_out_write", "_out_byte", "_print_f64"], r"""
# _print_f64p(d0 = valor, x0 = decimales): formato {:.N}
_print_f64p:
    stp  x29, x30, [sp, #-128]!
    mov  x29, sp
    str  x0, [sp, #24]
    fcmp d0, d0
    b.vs .Lpp_special
    fmov x9, d0
    lsl  x10, x9, #1
    movz x11, #0xffe0, lsl #48
    cmp  x10, x11
    b.eq .Lpp_special
    lsr  x10, x9, #63
    cbz  x10, .Lpp_abs
    str  d0, [sp, #16]
    mov  w0, #45
    bl   _out_byte
    ldr  d0, [sp, #16]
    fabs d0, d0
.Lpp_abs:
    ldr  x15, [sp, #24]
    fmov d4, #1.0
    fmov d5, #10.0
    mov  x13, #1
    mov  x14, #10
    mov  x10, x15
.Lpp_pow:
    cbz  x10, .Lpp_scaled
    fmul d4, d4, d5
    mul  x13, x13, x14
    sub  x10, x10, #1
    b    .Lpp_pow
.Lpp_scaled:
    fmul d3, d0, d4
    fcvtns x12, d3
    udiv x0, x12, x13
    msub x16, x0, x13, x12
    str  x16, [sp, #32]
    add  x1, sp, #128
    bl   _fmt_u64
    add  x1, sp, #128
    sub  x1, x1, x0
    bl   _out_write
    ldr  x15, [sp, #24]
    cbz  x15, .Lpp_ret
    mov  w0, #46
    bl   _out_byte
    ldr  x15, [sp, #24]
    ldr  x16, [sp, #32]
    add  x9, sp, #48
    add  x9, x9, x15
    mov  x10, x15
    mov  x11, #10
.Lpp_dig:
    udiv x12, x16, x11
    msub x13, x12, x11, x16
    add  w13, w13, #48
    sub  x9, x9, #1
    strb w13, [x9]
    mov  x16, x12
    subs x10, x10, #1
    b.ne .Lpp_dig
    mov  x0, x9
    ldr  x1, [sp, #24]
    bl   _out_write
.Lpp_ret:
    ldp  x29, x30, [sp], #128
    ret
.Lpp_special:
    ldp  x29, x30, [sp], #128
    b    _print_f64
""")

# ---------------------------------------------------------------------------
# Memoria
# ---------------------------------------------------------------------------
routine("_alloc", ["_panic"], r"""
# _alloc(x0 = bytes) -> x0 = puntero (16 alineado, memoria en cero). Heap "bump".
_alloc:
    add  x0, x0, #15
    and  x0, x0, #0xfffffffffffffff0
    adrp x9, _heap_cur
    ldr  x10, [x9, :lo12:_heap_cur]
    cbnz x10, .Lal_ok
    adrp x10, _heap
    add  x10, x10, :lo12:_heap
.Lal_ok:
    add  x11, x10, x0
    adrp x12, _heap_end
    add  x12, x12, :lo12:_heap_end
    cmp  x11, x12
    b.hi .Lal_oom
    str  x11, [x9, :lo12:_heap_cur]
    mov  x0, x10
    ret
.Lal_oom:
    adrp x0, _m_oom
    add  x0, x0, :lo12:_m_oom
    b    _panic
""")

routine("_memcpy", [], r"""
# _memcpy(x0 = destino, x1 = origen, x2 = bytes múltiplo de 8)
_memcpy:
    cbz  x2, .Lmc_done
.Lmc_loop:
    ldr  x9, [x1], #8
    str  x9, [x0], #8
    subs x2, x2, #8
    b.ne .Lmc_loop
.Lmc_done:
    ret
""")

routine("_arr_fill", [], r"""
# _arr_fill(x0 = destino, x1 = n, x2 = valor de 64 bits)
_arr_fill:
    cbz  x1, .Laf_done
.Laf_loop:
    str  x2, [x0], #8
    subs x1, x1, #1
    b.ne .Laf_loop
.Laf_done:
    ret
""")

routine("_arr_reverse", [], r"""
# _arr_reverse(x0 = datos, x1 = n elementos, x2 = bytes por elemento)
_arr_reverse:
    cmp  x1, #2
    b.lo .Lar_done
    mov  x3, #0
    sub  x4, x1, #1
.Lar_outer:
    cmp  x3, x4
    b.hs .Lar_done
    madd x5, x3, x2, x0
    madd x6, x4, x2, x0
    mov  x7, x2
.Lar_swap:
    ldr  x9, [x5]
    ldr  x10, [x6]
    str  x10, [x5], #8
    str  x9, [x6], #8
    subs x7, x7, #8
    b.ne .Lar_swap
    add  x3, x3, #1
    sub  x4, x4, #1
    b    .Lar_outer
.Lar_done:
    ret
""")

# ---------------------------------------------------------------------------
# Cadenas
# ---------------------------------------------------------------------------
routine("_str_ndup", ["_alloc"], r"""
# _str_ndup(x0 = origen, x1 = n) -> x0 = copia NUL-terminada de n bytes
_str_ndup:
    stp  x29, x30, [sp, #-32]!
    mov  x29, sp
    stp  x19, x20, [sp, #16]
    mov  x19, x0
    mov  x20, x1
    add  x0, x1, #1
    bl   _alloc
    mov  x9, x0
    mov  x10, x19
    mov  x11, x20
.Lnd_loop:
    cbz  x11, .Lnd_end
    ldrb w12, [x10], #1
    strb w12, [x9], #1
    sub  x11, x11, #1
    b    .Lnd_loop
.Lnd_end:
    strb wzr, [x9]
    ldp  x19, x20, [sp, #16]
    ldp  x29, x30, [sp], #32
    ret
""")

routine("_str_concat", ["_strlen", "_alloc"], r"""
# _str_concat(x0 = a, x1 = b) -> x0 = nueva cadena a+b
_str_concat:
    stp  x29, x30, [sp, #-48]!
    mov  x29, sp
    stp  x19, x20, [sp, #16]
    stp  x21, x22, [sp, #32]
    mov  x19, x0
    mov  x20, x1
    bl   _strlen
    mov  x21, x0
    mov  x0, x20
    bl   _strlen
    mov  x22, x0
    add  x0, x21, x22
    add  x0, x0, #1
    bl   _alloc
    mov  x9, x0
    mov  x10, x19
.Lcc_a:
    ldrb w11, [x10], #1
    cbz  w11, .Lcc_b0
    strb w11, [x9], #1
    b    .Lcc_a
.Lcc_b0:
    mov  x10, x20
.Lcc_b:
    ldrb w11, [x10], #1
    strb w11, [x9], #1
    cbnz w11, .Lcc_b
    ldp  x19, x20, [sp, #16]
    ldp  x21, x22, [sp, #32]
    ldp  x29, x30, [sp], #48
    ret
""")

routine("_str_cmp", [], r"""
# _str_cmp(x0 = a, x1 = b) -> x0 = -1, 0 ó 1 (orden lexicográfico por bytes)
_str_cmp:
.Lsc_loop:
    ldrb w2, [x0], #1
    ldrb w3, [x1], #1
    cmp  w2, w3
    b.ne .Lsc_diff
    cbnz w2, .Lsc_loop
    mov  x0, #0
    ret
.Lsc_diff:
    mov  x0, #1
    mov  x4, #-1
    csel x0, x4, x0, lo
    ret
""")

routine("_str_repeat", ["_strlen", "_alloc"], r"""
# _str_repeat(x0 = cadena, x1 = n) -> x0 = cadena repetida n veces
_str_repeat:
    stp  x29, x30, [sp, #-48]!
    mov  x29, sp
    stp  x19, x20, [sp, #16]
    stp  x21, x22, [sp, #32]
    mov  x19, x0
    cmp  x1, #0
    csel x20, xzr, x1, lt
    bl   _strlen
    mov  x21, x0
    mul  x0, x21, x20
    add  x0, x0, #1
    bl   _alloc
    mov  x22, x0
    mov  x9, x0
.Lrp_outer:
    cbz  x20, .Lrp_fin
    mov  x10, x19
.Lrp_inner:
    ldrb w11, [x10], #1
    cbz  w11, .Lrp_next
    strb w11, [x9], #1
    b    .Lrp_inner
.Lrp_next:
    sub  x20, x20, #1
    b    .Lrp_outer
.Lrp_fin:
    strb wzr, [x9]
    mov  x0, x22
    ldp  x19, x20, [sp, #16]
    ldp  x21, x22, [sp, #32]
    ldp  x29, x30, [sp], #48
    ret
""")

routine("_str_find", [], r"""
# _str_find(x0 = pajar, x1 = aguja) -> x0 = puntero a la primera coincidencia ó 0
_str_find:
    mov  x2, x0
.Lsf_outer:
    mov  x3, x2
    mov  x4, x1
.Lsf_inner:
    ldrb w5, [x4]
    cbz  w5, .Lsf_found
    ldrb w6, [x3]
    cbz  w6, .Lsf_none
    cmp  w5, w6
    b.ne .Lsf_next
    add  x3, x3, #1
    add  x4, x4, #1
    b    .Lsf_inner
.Lsf_next:
    add  x2, x2, #1
    b    .Lsf_outer
.Lsf_found:
    mov  x0, x2
    ret
.Lsf_none:
    mov  x0, #0
    ret
""")

routine("_str_contains", ["_str_find"], r"""
# _str_contains(x0 = pajar, x1 = aguja) -> x0 = 0/1
_str_contains:
    stp  x29, x30, [sp, #-16]!
    mov  x29, sp
    bl   _str_find
    cmp  x0, #0
    cset x0, ne
    ldp  x29, x30, [sp], #16
    ret
""")

routine("_str_replace", ["_strlen", "_alloc", "_str_find"], r"""
# _str_replace(x0 = s, x1 = a, x2 = b) -> x0 = s con cada 'a' reemplazada por 'b'
_str_replace:
    stp  x29, x30, [sp, #-96]!
    mov  x29, sp
    stp  x19, x20, [sp, #16]
    stp  x21, x22, [sp, #32]
    stp  x23, x24, [sp, #48]
    stp  x25, x26, [sp, #64]
    mov  x19, x0
    mov  x20, x1
    mov  x21, x2
    mov  x0, x20
    bl   _strlen
    mov  x22, x0                 // la
    mov  x0, x21
    bl   _strlen
    mov  x23, x0                 // lb
    mov  x0, x19
    bl   _strlen
    mov  x24, x0                 // ls
    mov  x25, #0                 // ocurrencias
    cbz  x22, .Lrr_alloc
    mov  x26, x19
.Lrr_count:
    mov  x0, x26
    mov  x1, x20
    bl   _str_find
    cbz  x0, .Lrr_alloc
    add  x25, x25, #1
    add  x26, x0, x22
    b    .Lrr_count
.Lrr_alloc:
    mul  x0, x25, x23
    add  x0, x0, x24
    mul  x1, x25, x22
    sub  x0, x0, x1
    add  x0, x0, #1
    bl   _alloc
    mov  x25, x0                 // inicio del resultado
    mov  x9, x0                  // cursor de destino
    mov  x26, x19                // cursor de origen
.Lrr_build:
    cbz  x22, .Lrr_tail
    mov  x0, x26
    mov  x1, x20
    bl   _str_find
    mov  x10, x0
    cbz  x10, .Lrr_tail
.Lrr_cp1:
    cmp  x26, x10
    b.hs .Lrr_cp1d
    ldrb w11, [x26], #1
    strb w11, [x9], #1
    b    .Lrr_cp1
.Lrr_cp1d:
    mov  x12, x21
.Lrr_cp2:
    ldrb w11, [x12], #1
    cbz  w11, .Lrr_cp2d
    strb w11, [x9], #1
    b    .Lrr_cp2
.Lrr_cp2d:
    add  x26, x10, x22
    b    .Lrr_build
.Lrr_tail:
    ldrb w11, [x26], #1
    strb w11, [x9], #1
    cbnz w11, .Lrr_tail
    mov  x0, x25
    ldp  x19, x20, [sp, #16]
    ldp  x21, x22, [sp, #32]
    ldp  x23, x24, [sp, #48]
    ldp  x25, x26, [sp, #64]
    ldp  x29, x30, [sp], #96
    ret
""")

routine("_str_upper", ["_strlen", "_alloc"], r"""
# _str_upper(x0) -> x0 = copia en mayúsculas (ASCII)
_str_upper:
    stp  x29, x30, [sp, #-32]!
    mov  x29, sp
    str  x19, [sp, #16]
    mov  x19, x0
    bl   _strlen
    add  x0, x0, #1
    bl   _alloc
    mov  x13, x0
    mov  x9, x0
    mov  x10, x19
.Lup_loop:
    ldrb w11, [x10], #1
    sub  w12, w11, #97
    cmp  w12, #25
    b.hi .Lup_st
    sub  w11, w11, #32
.Lup_st:
    strb w11, [x9], #1
    cbnz w11, .Lup_loop
    mov  x0, x13
    ldr  x19, [sp, #16]
    ldp  x29, x30, [sp], #32
    ret
""")

routine("_str_lower", ["_strlen", "_alloc"], r"""
# _str_lower(x0) -> x0 = copia en minúsculas (ASCII)
_str_lower:
    stp  x29, x30, [sp, #-32]!
    mov  x29, sp
    str  x19, [sp, #16]
    mov  x19, x0
    bl   _strlen
    add  x0, x0, #1
    bl   _alloc
    mov  x13, x0
    mov  x9, x0
    mov  x10, x19
.Llo_loop:
    ldrb w11, [x10], #1
    sub  w12, w11, #65
    cmp  w12, #25
    b.hi .Llo_st
    add  w11, w11, #32
.Llo_st:
    strb w11, [x9], #1
    cbnz w11, .Llo_loop
    mov  x0, x13
    ldr  x19, [sp, #16]
    ldp  x29, x30, [sp], #32
    ret
""")

routine("_str_split", ["_strlen", "_alloc", "_str_find", "_str_ndup"], r"""
# _str_split(x0 = s, x1 = separador) -> x0 = Vec<&str> (longitud en [ptr-8])
_str_split:
    stp  x29, x30, [sp, #-96]!
    mov  x29, sp
    stp  x19, x20, [sp, #16]
    stp  x21, x22, [sp, #32]
    stp  x23, x24, [sp, #48]
    stp  x25, x26, [sp, #64]
    mov  x19, x0
    mov  x20, x1
    mov  x0, x20
    bl   _strlen
    mov  x21, x0                 // longitud del separador
    mov  x22, #1                 // piezas
    cbz  x21, .Lss_alloc
    mov  x24, x19
.Lss_count:
    mov  x0, x24
    mov  x1, x20
    bl   _str_find
    cbz  x0, .Lss_alloc
    add  x22, x22, #1
    add  x24, x0, x21
    b    .Lss_count
.Lss_alloc:
    lsl  x0, x22, #3
    add  x0, x0, #8
    bl   _alloc
    str  x22, [x0]
    add  x23, x0, #8
    mov  x24, x19
    mov  x25, #0
.Lss_loop:
    cbz  x21, .Lss_last
    mov  x0, x24
    mov  x1, x20
    bl   _str_find
    cbz  x0, .Lss_last
    mov  x26, x0
    mov  x0, x24
    sub  x1, x26, x24
    bl   _str_ndup
    str  x0, [x23, x25, lsl #3]
    add  x25, x25, #1
    add  x24, x26, x21
    b    .Lss_loop
.Lss_last:
    mov  x0, x24
    bl   _strlen
    mov  x1, x0
    mov  x0, x24
    bl   _str_ndup
    str  x0, [x23, x25, lsl #3]
    mov  x0, x23
    ldp  x19, x20, [sp, #16]
    ldp  x21, x22, [sp, #32]
    ldp  x23, x24, [sp, #48]
    ldp  x25, x26, [sp, #64]
    ldp  x29, x30, [sp], #96
    ret
""")

routine("_str_split_ws", ["_alloc", "_str_ndup"], r"""
# _str_split_ws(x0 = s) -> x0 = Vec<&str> con las palabras separadas por espacios
_str_split_ws:
    stp  x29, x30, [sp, #-96]!
    mov  x29, sp
    stp  x19, x20, [sp, #16]
    stp  x21, x22, [sp, #32]
    stp  x23, x24, [sp, #48]
    stp  x25, x26, [sp, #64]
    mov  x19, x0
    mov  x22, #0
    mov  x24, x19
    mov  w10, #0
.Lsw_c:
    ldrb w9, [x24], #1
    cbz  w9, .Lsw_alloc
    cmp  w9, #32
    b.eq .Lsw_cws
    cmp  w9, #9
    b.lo .Lsw_cnw
    cmp  w9, #13
    b.ls .Lsw_cws
.Lsw_cnw:
    cbnz w10, .Lsw_c
    mov  w10, #1
    add  x22, x22, #1
    b    .Lsw_c
.Lsw_cws:
    mov  w10, #0
    b    .Lsw_c
.Lsw_alloc:
    lsl  x0, x22, #3
    add  x0, x0, #8
    bl   _alloc
    str  x22, [x0]
    add  x23, x0, #8
    mov  x24, x19
    mov  x25, #0
.Lsw_skip:
    ldrb w9, [x24]
    cbz  w9, .Lsw_fin
    cmp  w9, #32
    b.eq .Lsw_adv
    cmp  w9, #9
    b.lo .Lsw_word
    cmp  w9, #13
    b.hi .Lsw_word
.Lsw_adv:
    add  x24, x24, #1
    b    .Lsw_skip
.Lsw_word:
    mov  x26, x24
.Lsw_scan:
    ldrb w9, [x24]
    cbz  w9, .Lsw_end
    cmp  w9, #32
    b.eq .Lsw_end
    cmp  w9, #9
    b.lo .Lsw_next
    cmp  w9, #13
    b.ls .Lsw_end
.Lsw_next:
    add  x24, x24, #1
    b    .Lsw_scan
.Lsw_end:
    mov  x0, x26
    sub  x1, x24, x26
    bl   _str_ndup
    str  x0, [x23, x25, lsl #3]
    add  x25, x25, #1
    b    .Lsw_skip
.Lsw_fin:
    mov  x0, x23
    ldp  x19, x20, [sp, #16]
    ldp  x21, x22, [sp, #32]
    ldp  x23, x24, [sp, #48]
    ldp  x25, x26, [sp, #64]
    ldp  x29, x30, [sp], #96
    ret
""")

# ---------------------------------------------------------------------------
# Aleatorios, errores y salida
# ---------------------------------------------------------------------------
routine("_random", [], r"""
# _random(x0 = min, x1 = max) -> x0 en [min, max] (xorshift64, semilla getrandom)
_random:
    mov  x4, x0
    mov  x5, x1
    adrp x9, _rng
    add  x9, x9, :lo12:_rng
    ldr  x10, [x9]
    cbnz x10, .Lrn_go
    mov  x0, x9
    mov  x1, #8
    mov  x2, #0
    mov  x8, #278                // sys_getrandom
    svc  #0
    ldr  x10, [x9]
    cbnz x10, .Lrn_go
    mov  x10, #0x2545
    movk x10, #0xF491, lsl #16
    movk x10, #0x4F6C, lsl #32
    movk x10, #0xDD1D, lsl #48
.Lrn_go:
    lsl  x11, x10, #13
    eor  x10, x10, x11
    lsr  x11, x10, #7
    eor  x10, x10, x11
    lsl  x11, x10, #17
    eor  x10, x10, x11
    str  x10, [x9]
    sub  x6, x5, x4
    add  x6, x6, #1
    cmp  x6, #0
    b.le .Lrn_min
    udiv x7, x10, x6
    msub x7, x7, x6, x10
    add  x0, x4, x7
    sxtw x0, w0
    ret
.Lrn_min:
    mov  x0, x4
    ret
""")

routine("_exit", ["_flush"], r"""
# _exit(x0 = código): vacía la salida y termina el proceso
_exit:
    mov  x19, x0
    bl   _flush
    mov  x0, x19
    mov  x8, #93                 // sys_exit
    svc  #0
""")

routine("_panic", ["_exit", "_strlen"], r"""
# _panic(x0 = mensaje): imprime en stderr y termina con código 101
_panic:
    mov  x20, x0
    bl   _flush
    mov  x0, x20
    bl   _strlen
    mov  x2, x0
    mov  x1, x20
    mov  x0, #2
    mov  x8, #64
    svc  #0
    mov  x0, #101
    b    _exit
""")

routine("_panic_oob", ["_panic"], r"""
_panic_oob:
    adrp x0, _m_oob
    add  x0, x0, :lo12:_m_oob
    b    _panic
""")

routine("_panic_div0", ["_panic"], r"""
_panic_div0:
    adrp x0, _m_div0
    add  x0, x0, :lo12:_m_div0
    b    _panic
""")

# datos de apoyo del runtime (rutina -> directivas de datos)
DATA = {
    "_print_bool": '_s_true: .asciz "true"\n_s_false: .asciz "false"',
    "_print_f64": '_s_nan: .asciz "NaN"\n_s_inf: .asciz "inf"\n_s_dot0: .asciz ".0"',
    "_alloc": '_m_oom: .asciz "panic: memoria insuficiente (heap agotado)\\n"',
    "_panic_oob": '_m_oob: .asciz "panic: índice fuera de los límites del arreglo\\n"',
    "_panic_div0": '_m_div0: .asciz "panic: división entre cero\\n"',
}

# variables .data / .bss necesarias
NEEDS_OUT = {"_out_write", "_flush"}


def resolve(used):
    """Cierre transitivo de dependencias, en un orden estable."""
    seen, order = set(), []

    def visit(n):
        if n in seen:
            return
        seen.add(n)
        for d in DEPS[n]:
            visit(d)
        order.append(n)

    for n in sorted(used):
        visit(n)
    return order
