"""Análisis sintáctico de OxigenNative con PLY (yacc) y construcción del AST."""

import os

import ply.lex as plylex
import ply.yacc as yacc

from . import ast_nodes as A
from . import typesys as T
from .lexer import OxigenLexer, tokens as lexer_tokens

TOKEN_NAMES = {
    "SEMI": "';'", "RPAREN": "')'", "RBRACKET": "']'", "RBRACE": "'}'",
    "LBRACE": "'{'", "LPAREN": "'('", "COMMA": "','", "COLON": "':'",
}

# tokens que pueden terminar una expresión / declaración
END_TOKENS = {
    "ID", "STRUCT_NAME", "INT", "FLOAT", "STRING", "CHAR", "TRUE", "FALSE", "RPAREN", "RBRACE",
    "RBRACKET", "BREAK", "CONTINUE", "RETURN", "LABEL", "T_I32", "T_F64",
    "T_BOOL", "T_CHAR", "T_STRING", "T_STR", "GT", "UNDERSCORE",
}


class _TokenFeeder:
    """Envuelve al lexer: permite devolver tokens y recuerda los anteriores."""

    def __init__(self, lexer):
        self.lexer = lexer
        self.pending = []
        self.history = []

    @property
    def lineno(self):
        return self.lexer.lexer.lineno

    @property
    def lexpos(self):
        return self.lexer.lexer.lexpos

    def input(self, data):
        self.lexer.input(data)

    def token(self):
        if self.pending:
            return self.pending.pop()  # ya está en el historial
        tok = self.lexer.token()
        if tok is not None:
            tok.endpos = self.lexer.lexer.lexpos
            tok.endline = self.lexer.lexer.lineno
            self.history.append(tok)
            if len(self.history) > 16:
                self.history.pop(0)
        return tok

    def pushback(self, tok):
        self.pending.append(tok)

    def prev_of(self, tok):
        """Token inmediatamente anterior a `tok` (o el último si tok es EOF)."""
        h = self.history
        if tok is None:
            return h[-1] if h else None
        for i in range(len(h) - 1, -1, -1):
            if h[i] is tok:
                return h[i - 1] if i > 0 else None
        return h[-1] if h else None


class OxigenParser:
    tokens = [t for t in lexer_tokens if t != "BLOCK_COMMENT"]

    precedence = (
        ("nonassoc", "DOTDOT", "DOTDOTEQ"),
        ("left", "OR"),
        ("left", "AND"),
        ("left", "EQ", "NE"),
        ("left", "LT", "LE", "GT", "GE"),
        ("left", "PLUS", "MINUS"),
        ("left", "STAR", "SLASH", "PERCENT"),
        ("left", "AS"),
        ("right", "UMINUS", "UNOT", "UREF"),
    )

    start = "program"

    def __init__(self, errors, debug=False):
        self.errors = errors
        self.debug = debug
        outdir = os.path.dirname(os.path.abspath(__file__))
        self.parser = yacc.yacc(
            module=self, debug=debug, write_tables=True, outputdir=outdir,
            tabmodule="oxigen_parsetab",
            errorlog=None if debug else yacc.NullLogger(),
        )

    # ------------------------------------------------------------------
    def parse(self, source):
        self.source = source
        self.lexer = OxigenLexer(self.errors)
        self.feeder = _TokenFeeder(self.lexer)
        self.inserted = set()
        self.eof_inserts = 0
        return self.parser.parse(source, lexer=self.feeder, tracking=True)

    # utilidades -----------------------------------------------------------
    def col(self, pos):
        return pos - self.source.rfind("\n", 0, pos)

    def at(self, node, p, i):
        node.line = p.lineno(i)
        node.col = self.col(p.lexpos(i))
        return node

    @staticmethod
    def copy_pos(node, other):
        node.line, node.col = other.line, other.col
        return node

    # ======================================================================
    # Programa
    # ======================================================================
    def p_program(self, p):
        """program : items"""
        p[0] = A.Program(p[1])
        p[0].line, p[0].col = 1, 1

    def p_items(self, p):
        """items : items item
                 | empty"""
        if len(p) == 3:
            p[0] = p[1] + ([p[2]] if p[2] is not None else [])
        else:
            p[0] = []

    def p_empty(self, p):
        """empty :"""
        p[0] = None

    def p_item(self, p):
        """item : function
                | struct_decl
                | let_stmt"""
        p[0] = p[1]

    def p_item_error(self, p):
        """item : error RBRACE"""
        p[0] = None

    # ----------------------------------------------------------------------
    # Structs
    # ----------------------------------------------------------------------
    def p_struct_decl(self, p):
        """struct_decl : STRUCT STRUCT_NAME LBRACE field_decls RBRACE
                       | STRUCT ID LBRACE field_decls RBRACE"""
        p[0] = self.at(A.StructDecl(p[2], p[4]), p, 2)

    def p_field_decls(self, p):
        """field_decls : params
                       | params COMMA
                       | empty"""
        p[0] = p[1] if p[1] is not None else []

    def p_type_struct(self, p):
        """type : ID
                | STRUCT_NAME"""
        p[0] = T.struct_of(p[1])

    def p_primary_struct_lit(self, p):
        """primary : STRUCT_NAME LBRACE field_inits RBRACE"""
        p[0] = self.at(A.StructLit(p[1], p[3]), p, 1)

    def p_field_inits(self, p):
        """field_inits : field_init_list
                       | field_init_list COMMA
                       | empty"""
        p[0] = p[1] if p[1] is not None else []

    def p_field_init_list(self, p):
        """field_init_list : field_init
                           | field_init_list COMMA field_init"""
        p[0] = [p[1]] if len(p) == 2 else p[1] + [p[3]]

    def p_field_init(self, p):
        """field_init : ID COLON expr"""
        p[0] = (p[1], p[3], p.lineno(1), self.col(p.lexpos(1)))

    # ----------------------------------------------------------------------
    # Funciones
    # ----------------------------------------------------------------------
    def p_function(self, p):
        """function : FN ID LPAREN params_opt RPAREN block"""
        p[0] = self.at(A.Function(p[2], p[4], None, p[6]), p, 2)

    def p_function_ret(self, p):
        """function : FN ID LPAREN params_opt RPAREN ARROW type block"""
        p[0] = self.at(A.Function(p[2], p[4], p[7], p[8]), p, 2)

    def p_params_opt(self, p):
        """params_opt : params
                      | params COMMA
                      | empty"""
        p[0] = p[1] if p[1] is not None else []

    def p_params(self, p):
        """params : param
                  | params COMMA param"""
        p[0] = [p[1]] if len(p) == 2 else p[1] + [p[3]]

    def p_param(self, p):
        """param : ID COLON type"""
        p[0] = self.at(A.Param(p[1], p[3]), p, 1)

    # ----------------------------------------------------------------------
    # Tipos
    # ----------------------------------------------------------------------
    def p_type_simple(self, p):
        """type : T_I32
                | T_F64
                | T_BOOL
                | T_CHAR
                | T_STRING
                | T_STR"""
        p[0] = {
            "i32": T.I32, "f64": T.F64, "bool": T.BOOL, "char": T.CHAR,
            "String": T.STRING, "str": T.STRING,
        }[p[1]]

    def p_type_ref_str(self, p):
        """type : AMP T_STR"""
        p[0] = T.STRING

    def p_type_array(self, p):
        """type : LBRACKET type SEMI INT RBRACKET"""
        p[0] = T.array_of(p[2], p[4])

    def p_type_vec(self, p):
        """type : T_VEC LT type GT"""
        p[0] = T.vec_of(p[3])

    # ----------------------------------------------------------------------
    # Bloques y sentencias
    # ----------------------------------------------------------------------
    def p_block(self, p):
        """block : LBRACE stmts RBRACE"""
        p[0] = self.at(A.Block(p[2]), p, 1)

    def p_stmts(self, p):
        """stmts : stmts stmt
                 | empty"""
        if len(p) == 3:
            p[0] = p[1] + ([p[2]] if p[2] is not None else [])
        else:
            p[0] = []

    def p_stmt_simple(self, p):
        """stmt : let_stmt
                | if_stmt
                | while_stmt
                | loop_stmt
                | for_stmt
                | match_stmt
                | block"""
        p[0] = p[1]

    def p_stmt_error(self, p):
        """stmt : error SEMI"""
        p[0] = None

    def p_stmt_expr(self, p):
        """stmt : expr SEMI"""
        p[0] = self.copy_pos(A.ExprStmt(p[1]), p[1])

    def p_stmt_assign(self, p):
        """stmt : assign_core SEMI"""
        p[0] = p[1]

    def p_assign_core(self, p):
        """assign_core : expr assign_op expr"""
        target = p[1]
        if not isinstance(target, (A.Identifier, A.Index, A.FieldAccess)):
            self.errors.sintactico(
                "El lado izquierdo de una asignación debe ser una variable, un elemento de arreglo o un campo.",
                target.line, target.col, fatal=True)
        p[0] = self.copy_pos(A.Assign(target, p[2], p[3]), target)

    def p_assign_op(self, p):
        """assign_op : ASSIGN
                     | PLUSEQ
                     | MINUSEQ
                     | STAREQ
                     | SLASHEQ
                     | PERCENTEQ"""
        p[0] = p[1]

    def p_stmt_break(self, p):
        """stmt : BREAK SEMI
                | BREAK LABEL SEMI"""
        p[0] = self.at(A.Break(p[2] if len(p) == 4 else None), p, 1)

    def p_stmt_continue(self, p):
        """stmt : CONTINUE SEMI
                | CONTINUE LABEL SEMI"""
        p[0] = self.at(A.Continue(p[2] if len(p) == 4 else None), p, 1)

    def p_stmt_return(self, p):
        """stmt : RETURN SEMI
                | RETURN expr SEMI"""
        p[0] = self.at(A.Return(p[2] if len(p) == 4 else None), p, 1)

    # ---- let ---------------------------------------------------------------
    def p_let_head(self, p):
        """let_head : LET
                    | LET MUT"""
        p[0] = len(p) == 3

    def p_let_full(self, p):
        """let_stmt : let_head ID COLON type ASSIGN expr SEMI"""
        p[0] = self._let(p, p[1], p[2], p[4], p[6])

    def p_let_infer(self, p):
        """let_stmt : let_head ID ASSIGN expr SEMI"""
        p[0] = self._let(p, p[1], p[2], None, p[4])

    def p_let_typed(self, p):
        """let_stmt : let_head ID COLON type SEMI"""
        p[0] = self._let(p, p[1], p[2], p[4], None)

    def p_let_bare(self, p):
        """let_stmt : let_head ID SEMI"""
        p[0] = self._let(p, p[1], p[2], None, None)

    def _let(self, p, mutable, name, ann, init):
        node = A.VarDecl(name, mutable, ann, init)
        self.at(node, p, 1)
        node.name_line = p.lineno(2)
        node.name_col = self.col(p.lexpos(2))
        return node

    # ---- if / loops / match -----------------------------------------------
    def _check_cond(self, cond):
        if getattr(cond, "paren", False):
            self.errors.sintactico(
                "No se permiten paréntesis alrededor de la condición.",
                cond.line, cond.col, fatal=False)

    def p_if(self, p):
        """if_stmt : IF expr block
                   | IF expr block ELSE block
                   | IF expr block ELSE if_stmt"""
        self._check_cond(p[2])
        p[0] = self.at(A.If(p[2], p[3], p[5] if len(p) == 6 else None), p, 1)

    def p_while(self, p):
        """while_stmt : WHILE expr block"""
        self._check_cond(p[2])
        p[0] = self.at(A.While(p[2], p[3]), p, 1)

    def p_while_label(self, p):
        """while_stmt : LABEL COLON WHILE expr block"""
        self._check_cond(p[4])
        p[0] = self.at(A.While(p[4], p[5], label=p[1]), p, 1)

    def p_loop(self, p):
        """loop_stmt : LOOP block"""
        p[0] = self.at(A.Loop(p[2]), p, 1)

    def p_loop_label(self, p):
        """loop_stmt : LABEL COLON LOOP block"""
        p[0] = self.at(A.Loop(p[4], label=p[1]), p, 1)

    def p_for(self, p):
        """for_stmt : FOR ID IN expr block"""
        p[0] = self.at(A.For(p[2], p[4], p[5]), p, 1)

    def p_for_label(self, p):
        """for_stmt : LABEL COLON FOR ID IN expr block"""
        p[0] = self.at(A.For(p[4], p[6], p[7], label=p[1]), p, 1)

    def p_match(self, p):
        """match_stmt : MATCH expr LBRACE arms RBRACE"""
        p[0] = self.at(A.Match(p[2], p[4]), p, 1)

    def p_arms(self, p):
        """arms : arms arm
                | arm"""
        p[0] = [p[1]] if len(p) == 2 else p[1] + [p[2]]

    def p_arm_block(self, p):
        """arm : patterns FATARROW block opt_comma"""
        p[0] = self.copy_pos(A.MatchArm(p[1], p[3]), p[1][0])

    def p_arm_stmt(self, p):
        """arm : patterns FATARROW arm_stmt opt_comma"""
        body = A.Block([p[3]])
        self.copy_pos(body, p[3])
        p[0] = self.copy_pos(A.MatchArm(p[1], body), p[1][0])

    def p_opt_comma(self, p):
        """opt_comma : COMMA
                     | empty"""
        p[0] = None

    def p_arm_body_expr(self, p):
        """arm_stmt : expr"""
        p[0] = self.copy_pos(A.ExprStmt(p[1]), p[1])

    def p_arm_body_assign(self, p):
        """arm_stmt : assign_core"""
        p[0] = p[1]

    def p_arm_body_break(self, p):
        """arm_stmt : BREAK
                    | BREAK LABEL"""
        p[0] = self.at(A.Break(p[2] if len(p) == 3 else None), p, 1)

    def p_arm_body_continue(self, p):
        """arm_stmt : CONTINUE
                    | CONTINUE LABEL"""
        p[0] = self.at(A.Continue(p[2] if len(p) == 3 else None), p, 1)

    def p_arm_body_return(self, p):
        """arm_stmt : RETURN
                    | RETURN expr"""
        p[0] = self.at(A.Return(p[2] if len(p) == 3 else None), p, 1)

    def p_patterns(self, p):
        """patterns : pattern
                    | patterns PIPE pattern"""
        p[0] = [p[1]] if len(p) == 2 else p[1] + [p[3]]

    def p_pattern_wild(self, p):
        """pattern : UNDERSCORE"""
        p[0] = self.at(A.Wildcard(), p, 1)

    def p_pattern_expr(self, p):
        """pattern : expr"""
        p[0] = p[1]

    # ======================================================================
    # Expresiones
    # ======================================================================
    def p_expr_binary(self, p):
        """expr : expr OR expr
                | expr AND expr
                | expr EQ expr
                | expr NE expr
                | expr LT expr
                | expr LE expr
                | expr GT expr
                | expr GE expr
                | expr PLUS expr
                | expr MINUS expr
                | expr STAR expr
                | expr SLASH expr
                | expr PERCENT expr"""
        node = A.Binary(p[2], p[1], p[3])
        self.copy_pos(node, p[1])
        node.op_line, node.op_col = p.lineno(2), self.col(p.lexpos(2))
        p[0] = node

    def p_expr_range(self, p):
        """expr : expr DOTDOT expr
                | expr DOTDOTEQ expr"""
        p[0] = self.copy_pos(A.Range(p[1], p[3], p[2] == "..="), p[1])

    def p_expr_cast(self, p):
        """expr : expr AS type"""
        p[0] = self.copy_pos(A.Cast(p[1], p[3]), p[1])

    def p_expr_unary(self, p):
        """expr : unary"""
        p[0] = p[1]

    def p_unary_neg(self, p):
        """unary : MINUS unary %prec UMINUS"""
        p[0] = self.at(A.Unary("-", p[2]), p, 1)

    def p_unary_not(self, p):
        """unary : NOT unary %prec UNOT"""
        p[0] = self.at(A.Unary("!", p[2]), p, 1)

    def p_unary_ref(self, p):
        """unary : AMP unary %prec UREF"""
        operand = p[2]
        if isinstance(operand, A.Index) and isinstance(operand.index, A.Range):
            rng = operand.index
            node = A.SliceExpr(operand.base, 0, 0, rng.lo, rng.hi)
            node.inclusive = rng.inclusive
            p[0] = self.at(node, p, 1)
        else:
            p[0] = operand  # &x  ->  x  (préstamo sin semántica adicional)

    def p_unary_postfix(self, p):
        """unary : postfix"""
        p[0] = p[1]

    def p_postfix_primary(self, p):
        """postfix : primary"""
        p[0] = p[1]

    def p_postfix_index(self, p):
        """postfix : postfix LBRACKET expr RBRACKET"""
        p[0] = self.copy_pos(A.Index(p[1], p[3]), p[1])

    def p_postfix_method(self, p):
        """postfix : postfix DOT ID LPAREN args_opt RPAREN"""
        node = A.MethodCall(p[1], p[3], p[5])
        self.copy_pos(node, p[1])
        node.name_line, node.name_col = p.lineno(3), self.col(p.lexpos(3))
        p[0] = node

    def p_postfix_field(self, p):
        """postfix : postfix DOT ID"""
        node = A.FieldAccess(p[1], p[3])
        self.copy_pos(node, p[1])
        node.name_line, node.name_col = p.lineno(3), self.col(p.lexpos(3))
        p[0] = node

    # ---- primarios --------------------------------------------------------
    def p_primary_int(self, p):
        """primary : INT"""
        p[0] = self.at(A.Literal("i32", p[1]), p, 1)

    def p_primary_float(self, p):
        """primary : FLOAT"""
        p[0] = self.at(A.Literal("f64", p[1]), p, 1)

    def p_primary_string(self, p):
        """primary : STRING"""
        p[0] = self.at(A.Literal("String", p[1]), p, 1)

    def p_primary_char(self, p):
        """primary : CHAR"""
        p[0] = self.at(A.Literal("char", p[1]), p, 1)

    def p_primary_bool(self, p):
        """primary : TRUE
                   | FALSE"""
        p[0] = self.at(A.Literal("bool", p[1] == "true"), p, 1)

    def p_primary_id(self, p):
        """primary : ID"""
        p[0] = self.at(A.Identifier(p[1]), p, 1)

    def p_primary_call(self, p):
        """primary : ID LPAREN args_opt RPAREN"""
        p[0] = self.at(A.Call(p[1], p[3]), p, 1)

    def p_primary_paren(self, p):
        """primary : LPAREN expr RPAREN"""
        node = p[2]
        node.paren = True
        p[0] = node

    def p_primary_static(self, p):
        """primary : T_STRING COLONCOLON ID LPAREN args_opt RPAREN"""
        p[0] = self.at(A.StaticCall("String", p[3], p[5]), p, 1)

    def p_primary_println(self, p):
        """primary : PRINTLN LPAREN args_opt RPAREN"""
        p[0] = self.at(A.Println(p[3], True), p, 1)

    def p_primary_print(self, p):
        """primary : PRINT LPAREN args_opt RPAREN"""
        p[0] = self.at(A.Println(p[3], False), p, 1)

    def p_primary_array(self, p):
        """primary : LBRACKET RBRACKET
                   | LBRACKET expr_list RBRACKET
                   | LBRACKET expr_list COMMA RBRACKET"""
        elems = [] if len(p) == 3 else p[2]
        p[0] = self.at(A.ArrayLit(elems), p, 1)

    def p_primary_array_repeat(self, p):
        """primary : LBRACKET expr SEMI INT RBRACKET"""
        p[0] = self.at(A.ArrayRepeat(p[2], p[4]), p, 1)

    def p_args_opt(self, p):
        """args_opt : expr_list
                    | expr_list COMMA
                    | empty"""
        p[0] = p[1] if p[1] is not None else []

    def p_expr_list(self, p):
        """expr_list : expr
                     | expr_list COMMA expr"""
        p[0] = [p[1]] if len(p) == 2 else p[1] + [p[3]]

    # ======================================================================
    # Manejo de errores sintácticos
    # ======================================================================
    def _describe(self, tok):
        if tok is None:
            return "fin de archivo"
        return f"'{self.source[tok.lexpos:tok.endpos]}'"

    def _end_pos(self, tok):
        """(línea, columna) inmediatamente después del token `tok`."""
        end = tok.endpos
        return tok.endline, end - self.source.rfind("\n", 0, end)

    def _synthetic(self, ttype, value, near):
        t = plylex.LexToken()
        t.type, t.value = ttype, value
        t.lineno = getattr(near, "endline", 1) if near else 1
        t.lexpos = getattr(near, "endpos", 0) if near else 0
        t.endpos = t.lexpos
        t.endline = t.lineno
        return t

    def p_error(self, tok):
        parser = self.parser
        state = parser.statestack[-1]
        expected = set(parser.action.get(state, {}).keys())

        ins = None
        prev_tok = self.feeder.prev_of(tok)
        if True:
            if ("SEMI" in expected and prev_tok is not None
                    and prev_tok.type in END_TOKENS
                    and (tok is None or tok.type in (
                        "LET", "ID", "PRINTLN", "PRINT", "IF", "WHILE", "LOOP", "FOR",
                        "MATCH", "BREAK", "CONTINUE", "RETURN", "RBRACE", "LBRACE",
                        "LABEL", "FN") or tok.lineno > prev_tok.endline)):
                ins = "SEMI"
            elif "RPAREN" in expected and tok is not None and tok.type in ("SEMI", "LBRACE", "RBRACE", "RBRACKET"):
                ins = "RPAREN"
            elif "RBRACKET" in expected and tok is not None and tok.type in ("SEMI", "RPAREN", "RBRACE"):
                ins = "RBRACKET"
            elif "RBRACE" in expected and tok is None:
                ins = "RBRACE"

        if ins is not None:
            key = (tok.lexpos if tok is not None else -1, ins)
            if tok is None:
                self.eof_inserts += 1
                if self.eof_inserts > 100:
                    ins = None
            elif key in self.inserted:
                ins = None
            else:
                self.inserted.add(key)

        if ins is not None:
            symbol = {"SEMI": ";", "RPAREN": ")", "RBRACKET": "]", "RBRACE": "}"}[ins]
            if prev_tok is not None:
                line, col = self._end_pos(prev_tok)
            else:
                line, col = 1, 1
            self.errors.sintactico(f"Se esperaba '{symbol}'.", line, col, fatal=False)
            synthetic = self._synthetic(ins, symbol, prev_tok)
            if tok is not None:
                self.feeder.pushback(tok)
            parser.errok()
            return synthetic

        # error no recuperable por inserción
        if tok is None:
            last = self.feeder.prev_of(None)
            line, col = self._end_pos(last) if last else (1, 1)
            self.errors.sintactico("Fin de archivo inesperado.", line, col, fatal=True)
        else:
            exp = [TOKEN_NAMES[t] for t in ("SEMI", "RPAREN", "RBRACE", "RBRACKET") if t in expected]
            hint = f" Se esperaba {exp[0]}." if len(exp) == 1 else ""
            self.errors.sintactico(
                f"Token inesperado {self._describe(tok)}.{hint}",
                tok.lineno, self.col(tok.lexpos), fatal=True)
        return None


def parse_source(source, errors, debug=False):
    parser = OxigenParser(errors, debug=debug)
    return parser.parse(source)
