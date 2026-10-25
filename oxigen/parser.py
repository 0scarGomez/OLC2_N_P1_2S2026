"""Analizador sintáctico de OxigenNative (PLY / LALR(1)) que construye el AST propio."""
import threading

import ply.lex as lex
import ply.yacc as yacc

from . import ast_nodes as A
from . import types as T
from .errors import SINTACTICO, SEMANTICO
from .lexer import OxLexer, line_col


class TokenStream:
    """Envuelve al lexer para conocer el final del token previo y el balance de llaves."""

    def __init__(self, lexer, text):
        self.lexer = lexer
        self.text = text
        self.depth = 0
        self.prev_end = 0
        self.cur_end = 0
        self.pending = []
        self.injected = 0
        self.eof_depth = None

    def token(self):
        if self.pending:
            return self.pending.pop(0)
        t = self.lexer.token()
        if t is None:
            return None
        self.prev_end = self.cur_end
        self.cur_end = self.lexer.lexer.lexpos
        if t.type == "LBRACE":
            self.depth += 1
        elif t.type == "RBRACE":
            self.depth -= 1
        return t

    def make_rbrace(self):
        t = lex.LexToken()
        t.type = "RBRACE"
        t.value = "}"
        t.lineno = 0
        t.lexpos = len(self.text)
        return t


class OxParser:
    tokens = OxLexer.tokens

    precedence = (
        ("left", "OR"),
        ("left", "AND"),
        ("nonassoc", "EQ", "NE"),
        ("nonassoc", "LT", "GT", "LE", "GE"),
        ("left", "PLUS", "MINUS"),
        ("left", "TIMES", "DIVIDE", "MOD"),
        ("right", "UMINUS", "NOT"),
    )

    start = "program"

    def __init__(self):
        self.errors = None
        self.text = ""
        self.stream = None
        self.parser = yacc.yacc(module=self, write_tables=False, debug=False,
                                errorlog=yacc.NullLogger())

    # ------------------------------------------------------------------ API
    def parse(self, text, errors):
        self.errors = errors
        self.text = text
        lexer = OxLexer(errors).build()
        lexer.input(text)
        self.stream = TokenStream(lexer, text)
        return self.parser.parse(lexer=self.stream)

    # ------------------------------------------------------------------ utilidades
    def tpos(self, p, i):
        return line_col(self.text, p.lexpos(i))

    def _err(self, desc, line, col):
        self.errors.add(SINTACTICO, desc, line, col)

    # ------------------------------------------------------------------ programa
    def p_program(self, p):
        """program : item_list"""
        p[0] = A.Program(p[1], pos=(1, 1))

    def p_program_empty(self, p):
        """program : empty"""
        p[0] = A.Program([], pos=(1, 1))

    def p_empty(self, p):
        """empty :"""
        p[0] = None

    def p_item_list_many(self, p):
        """item_list : item_list item"""
        p[0] = p[1] + [p[2]]

    def p_item_list_one(self, p):
        """item_list : item"""
        p[0] = [p[1]]

    def p_item_fn(self, p):
        """item : FN ID LPAREN param_list_opt RPAREN ret_opt block"""
        p[0] = A.FunctionDecl(p[2], p[4], p[6], p[7], pos=self.tpos(p, 2))

    def p_param_list_opt(self, p):
        """param_list_opt : param_list
                          | empty"""
        p[0] = p[1] or []

    def p_param_list(self, p):
        """param_list : param_list COMMA param
                      | param"""
        p[0] = p[1] + [p[3]] if len(p) == 4 else [p[1]]

    def p_param(self, p):
        """param : ID COLON type"""
        p[0] = A.Param(p[1], p[3], pos=self.tpos(p, 1))

    def p_ret_opt(self, p):
        """ret_opt : ARROW type
                   | empty"""
        p[0] = p[2] if len(p) == 3 else None

    # ------------------------------------------------------------------ tipos
    def p_type_prim(self, p):
        """type : I32
                | F64
                | BOOL
                | CHAR
                | STRING_T
                | STR_T"""
        p[0] = {"i32": T.I32, "f64": T.F64, "bool": T.BOOL, "char": T.CHAR,
                "String": T.STRING, "str": T.STRING}[p[1]]

    def p_type_ref_str(self, p):
        """type : AMP STR_T"""
        p[0] = T.STRING

    def p_type_array(self, p):
        """type : LBRACKET type SEMI INT RBRACKET"""
        p[0] = T.ArrayType(p[2], p[4])

    def p_type_generic(self, p):
        """type : ID LT type GT"""
        if p[1] != "Vec":
            line, col = self.tpos(p, 1)
            self.errors.add(SEMANTICO, f"Tipo desconocido '{p[1]}'.", line, col)
            p[0] = T.NONE
        else:
            p[0] = T.VecType(p[3])

    # ------------------------------------------------------------------ bloques y sentencias
    def p_block(self, p):
        """block : LBRACE stmt_list RBRACE"""
        p[0] = A.Block([s for s in p[2] if s is not None], pos=self.tpos(p, 1))

    def p_stmt_list_many(self, p):
        """stmt_list : stmt_list statement"""
        p[0] = p[1] + [p[2]]

    def p_stmt_list_empty(self, p):
        """stmt_list : empty"""
        p[0] = []

    def p_statement_var(self, p):
        """statement : var_decl SEMI"""
        p[0] = p[1]

    def p_statement_assign(self, p):
        """statement : expr assign_op expr SEMI"""
        op, pos = p[2]
        p[0] = A.Assign(p[1], op, p[3], pos=pos)

    def p_statement_expr(self, p):
        """statement : expr SEMI"""
        p[0] = A.ExprStmt(p[1], pos=p[1].pos)

    def p_statement_println(self, p):
        """statement : println_stmt SEMI"""
        p[0] = p[1]

    def p_statement_ctrl(self, p):
        """statement : if_stmt
                     | while_stmt
                     | loop_stmt
                     | match_stmt
                     | block"""
        p[0] = p[1]

    def p_statement_break(self, p):
        """statement : BREAK opt_label SEMI"""
        p[0] = A.Break(p[2], pos=self.tpos(p, 1))

    def p_statement_continue(self, p):
        """statement : CONTINUE opt_label SEMI"""
        p[0] = A.Continue(p[2], pos=self.tpos(p, 1))

    def p_statement_return(self, p):
        """statement : RETURN SEMI"""
        p[0] = A.Return(None, pos=self.tpos(p, 1))

    def p_statement_return_expr(self, p):
        """statement : RETURN expr SEMI"""
        p[0] = A.Return(p[2], pos=self.tpos(p, 1))

    def p_statement_error(self, p):
        """statement : error SEMI"""
        p[0] = None

    def p_opt_label(self, p):
        """opt_label : LABEL
                     | empty"""
        p[0] = p[1]

    # -- declaración de variables
    def p_let_kw(self, p):
        """let_kw : LET
                  | LET MUT"""
        p[0] = (len(p) == 3, self.tpos(p, 1))

    def p_var_decl_full(self, p):
        """var_decl : let_kw ID COLON type ASSIGN expr"""
        p[0] = A.VarDecl(p[2], p[1][0], p[4], p[6], pos=self.tpos(p, 2))

    def p_var_decl_infer(self, p):
        """var_decl : let_kw ID ASSIGN expr"""
        p[0] = A.VarDecl(p[2], p[1][0], None, p[4], pos=self.tpos(p, 2))

    def p_var_decl_noinit(self, p):
        """var_decl : let_kw ID COLON type"""
        p[0] = A.VarDecl(p[2], p[1][0], p[4], None, pos=self.tpos(p, 2))

    def p_var_decl_bare(self, p):
        """var_decl : let_kw ID"""
        p[0] = A.VarDecl(p[2], p[1][0], None, None, pos=self.tpos(p, 2))

    def p_assign_op(self, p):
        """assign_op : ASSIGN
                     | PLUSEQ
                     | MINUSEQ
                     | TIMESEQ
                     | DIVEQ
                     | MODEQ"""
        p[0] = (p[1], self.tpos(p, 1))

    # -- println!
    def p_println(self, p):
        """println_stmt : PRINTLN LPAREN arg_list_opt RPAREN
                        | PRINT LPAREN arg_list_opt RPAREN"""
        p[0] = A.Println(p[3], p.slice[1].type == "PRINTLN", pos=self.tpos(p, 1))

    # -- if / while / loop
    def _check_cond(self, cond):
        if getattr(cond, "paren", False):
            line, col = cond.pos
            self._err("No se permiten paréntesis alrededor de la condición.", line, col)

    def p_if(self, p):
        """if_stmt : IF expr block"""
        self._check_cond(p[2])
        p[0] = A.If(p[2], p[3], None, pos=self.tpos(p, 1))

    def p_if_else(self, p):
        """if_stmt : IF expr block ELSE block
                   | IF expr block ELSE if_stmt"""
        self._check_cond(p[2])
        p[0] = A.If(p[2], p[3], p[5], pos=self.tpos(p, 1))

    def p_while(self, p):
        """while_stmt : WHILE expr block"""
        self._check_cond(p[2])
        p[0] = A.While(None, p[2], p[3], pos=self.tpos(p, 1))

    def p_while_label(self, p):
        """while_stmt : LABEL COLON WHILE expr block"""
        self._check_cond(p[4])
        p[0] = A.While(p[1], p[4], p[5], pos=self.tpos(p, 1))

    def p_loop(self, p):
        """loop_stmt : LOOP block"""
        p[0] = A.Loop(None, p[2], pos=self.tpos(p, 1))

    def p_loop_label(self, p):
        """loop_stmt : LABEL COLON LOOP block"""
        p[0] = A.Loop(p[1], p[4], pos=self.tpos(p, 1))

    # -- match
    def p_match(self, p):
        """match_stmt : MATCH expr LBRACE match_arms RBRACE"""
        p[0] = A.Match(p[2], p[4], pos=self.tpos(p, 1))

    def p_match_arms(self, p):
        """match_arms : match_arms match_arm
                      | match_arm"""
        p[0] = p[1] + [p[2]] if len(p) == 3 else [p[1]]

    def p_match_arm_block(self, p):
        """match_arm : pattern_list FATARROW block opt_comma"""
        p[0] = A.MatchArm(p[1], p[3], pos=p[1][0].pos)

    def p_match_arm_simple(self, p):
        """match_arm : pattern_list FATARROW simple_arm opt_comma"""
        p[0] = A.MatchArm(p[1], A.Block([p[3]], pos=p[3].pos), pos=p[1][0].pos)

    def p_opt_comma(self, p):
        """opt_comma : COMMA
                     | empty"""
        p[0] = None

    def p_simple_arm_expr(self, p):
        """simple_arm : expr"""
        p[0] = A.ExprStmt(p[1], pos=p[1].pos)

    def p_simple_arm_assign(self, p):
        """simple_arm : expr assign_op expr"""
        op, pos = p[2]
        p[0] = A.Assign(p[1], op, p[3], pos=pos)

    def p_simple_arm_println(self, p):
        """simple_arm : println_stmt"""
        p[0] = p[1]

    def p_simple_arm_break(self, p):
        """simple_arm : BREAK opt_label"""
        p[0] = A.Break(p[2], pos=self.tpos(p, 1))

    def p_simple_arm_continue(self, p):
        """simple_arm : CONTINUE opt_label"""
        p[0] = A.Continue(p[2], pos=self.tpos(p, 1))

    def p_simple_arm_return(self, p):
        """simple_arm : RETURN"""
        p[0] = A.Return(None, pos=self.tpos(p, 1))

    def p_simple_arm_return_expr(self, p):
        """simple_arm : RETURN expr"""
        p[0] = A.Return(p[2], pos=self.tpos(p, 1))

    def p_pattern_list(self, p):
        """pattern_list : pattern_list PIPE pattern
                        | pattern"""
        p[0] = p[1] + [p[3]] if len(p) == 4 else [p[1]]

    def p_pattern_int(self, p):
        """pattern : INT"""
        p[0] = A.IntLit(p[1], pos=self.tpos(p, 1))

    def p_pattern_neg_int(self, p):
        """pattern : MINUS INT"""
        p[0] = A.IntLit(-p[2], pos=self.tpos(p, 1))

    def p_pattern_float(self, p):
        """pattern : FLOAT"""
        p[0] = A.FloatLit(p[1], pos=self.tpos(p, 1))

    def p_pattern_neg_float(self, p):
        """pattern : MINUS FLOAT"""
        p[0] = A.FloatLit(-p[2], pos=self.tpos(p, 1))

    def p_pattern_str(self, p):
        """pattern : STRING"""
        p[0] = A.StrLit(p[1], pos=self.tpos(p, 1))

    def p_pattern_char(self, p):
        """pattern : CHAR_LIT"""
        p[0] = A.CharLit(p[1], pos=self.tpos(p, 1))

    def p_pattern_bool(self, p):
        """pattern : TRUE
                   | FALSE"""
        p[0] = A.BoolLit(p[1] == "true", pos=self.tpos(p, 1))

    def p_pattern_wild(self, p):
        """pattern : WILDCARD"""
        p[0] = A.Wildcard(pos=self.tpos(p, 1))

    # ------------------------------------------------------------------ expresiones
    def p_expr_binary(self, p):
        """expr : expr PLUS expr
                | expr MINUS expr
                | expr TIMES expr
                | expr DIVIDE expr
                | expr MOD expr
                | expr EQ expr
                | expr NE expr
                | expr LT expr
                | expr GT expr
                | expr LE expr
                | expr GE expr
                | expr AND expr
                | expr OR expr"""
        p[0] = A.Binary(p[2], p[1], p[3], pos=self.tpos(p, 2))

    def p_expr_uminus(self, p):
        """expr : MINUS expr %prec UMINUS"""
        p[0] = A.Unary("-", p[2], pos=self.tpos(p, 1))

    def p_expr_not(self, p):
        """expr : NOT expr"""
        p[0] = A.Unary("!", p[2], pos=self.tpos(p, 1))

    def p_expr_slice(self, p):
        """expr : AMP postfix LBRACKET INT DOTDOT INT RBRACKET"""
        p[0] = A.Slice(p[2], p[4], p[6], pos=self.tpos(p, 1))

    def p_expr_postfix(self, p):
        """expr : postfix"""
        p[0] = p[1]

    def p_postfix_primary(self, p):
        """postfix : primary"""
        p[0] = p[1]

    def p_postfix_index(self, p):
        """postfix : postfix LBRACKET expr RBRACKET"""
        p[0] = A.Index(p[1], p[3], pos=p[1].pos)

    def p_postfix_method(self, p):
        """postfix : postfix DOT ID LPAREN arg_list_opt RPAREN"""
        p[0] = A.MethodCall(p[1], p[3], p[5], pos=self.tpos(p, 3))

    def p_primary_int(self, p):
        """primary : INT"""
        p[0] = A.IntLit(p[1], pos=self.tpos(p, 1))

    def p_primary_float(self, p):
        """primary : FLOAT"""
        p[0] = A.FloatLit(p[1], pos=self.tpos(p, 1))

    def p_primary_string(self, p):
        """primary : STRING"""
        p[0] = A.StrLit(p[1], pos=self.tpos(p, 1))

    def p_primary_char(self, p):
        """primary : CHAR_LIT"""
        p[0] = A.CharLit(p[1], pos=self.tpos(p, 1))

    def p_primary_bool(self, p):
        """primary : TRUE
                   | FALSE"""
        p[0] = A.BoolLit(p[1] == "true", pos=self.tpos(p, 1))

    def p_primary_id(self, p):
        """primary : ID"""
        p[0] = A.Identifier(p[1], pos=self.tpos(p, 1))

    def p_primary_call(self, p):
        """primary : ID LPAREN arg_list_opt RPAREN"""
        p[0] = A.Call(p[1], p[3], pos=self.tpos(p, 1))

    def p_primary_paren(self, p):
        """primary : LPAREN expr RPAREN"""
        p[2].paren = True
        p[0] = p[2]

    def p_primary_array(self, p):
        """primary : LBRACKET expr_list RBRACKET
                   | LBRACKET expr_list COMMA RBRACKET"""
        p[0] = A.ArrayLit(p[2], pos=self.tpos(p, 1))

    def p_primary_array_repeat(self, p):
        """primary : LBRACKET expr SEMI INT RBRACKET"""
        p[0] = A.ArrayRepeat(p[2], p[4], pos=self.tpos(p, 1))

    def p_primary_string_ctor(self, p):
        """primary : STRING_T COLONCOLON ID LPAREN arg_list_opt RPAREN"""
        line, col = self.tpos(p, 1)
        name, args = p[3], p[5]
        if name == "from" and len(args) == 1:
            p[0] = A.StringFrom(args[0], pos=(line, col))
        elif name == "new" and not args:
            p[0] = A.StringNew(pos=(line, col))
        else:
            self.errors.add(SEMANTICO, f"La función 'String::{name}' no existe o recibe argumentos incorrectos.",
                            line, col)
            p[0] = A.StringNew(pos=(line, col))

    def p_expr_list(self, p):
        """expr_list : expr_list COMMA expr
                     | expr"""
        p[0] = p[1] + [p[3]] if len(p) == 4 else [p[1]]

    def p_arg_list_opt(self, p):
        """arg_list_opt : expr_list
                        | empty"""
        p[0] = p[1] or []

    # ------------------------------------------------------------------ errores sintácticos
    def p_error(self, tok):
        s = self.stream
        state = self.parser.statestack[-1]
        expected = set(self.parser.action.get(state, {}).keys()) - {"$end", "error"}

        if tok is None:                         # fin de archivo prematuro
            line, col = line_col(self.text, s.cur_end)
            if s.depth > 0 and s.injected < 200:
                if s.injected == 0:
                    self._err("Se esperaba '}'.", line, col)
                s.injected += 1
                s.depth -= 1
                self.parser.errok()
                return s.make_rbrace()
            if s.injected == 0:
                self._err("Fin de archivo inesperado.", line, col)
            return None

        text_of = tok.value if isinstance(tok.value, str) else str(tok.value)
        if "SEMI" in expected and tok.type != "SEMI":
            line, col = line_col(self.text, s.prev_end)
            self._err("Se esperaba ';'.", line, col)
        elif "RPAREN" in expected and tok.type != "RPAREN":
            line, col = line_col(self.text, tok.lexpos)
            self._err("Se esperaba ')'.", line, col)
        elif "RBRACKET" in expected and tok.type != "RBRACKET":
            line, col = line_col(self.text, tok.lexpos)
            self._err("Se esperaba ']'.", line, col)
        elif "LBRACE" in expected and tok.type != "LBRACE" and len(expected) <= 2:
            line, col = line_col(self.text, tok.lexpos)
            self._err("Se esperaba '{'.", line, col)
        else:
            line, col = line_col(self.text, tok.lexpos)
            self._err(f"Token inesperado '{text_of}'.", line, col)
        return None


_instance = None
_lock = threading.Lock()


def parse(text, errors):
    """Parsea `text`; devuelve el AST (Program) o None si no pudo recuperarse."""
    global _instance
    with _lock:
        if _instance is None:
            _instance = OxParser()
        return _instance.parse(text, errors)
