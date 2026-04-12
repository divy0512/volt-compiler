"""
VOLT Compiler — Python Backend
6 Phases: Lexer → Parser → Semantic → IR Gen → Optimizer → Code Gen
"""

import json
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="VOLT Compiler API",
    description="6-phase compiler: Lexer → Parser → Semantic → IR Gen → Optimizer → Code Gen",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

KEYWORDS = {'fn','let','return','if','else','while','true','false','print',
            'int','float','bool','string','void'}

# ─────────────────────────────────────────────
# PHASE 1: LEXER
# ─────────────────────────────────────────────
def lex(src):
    tokens = []
    i = 0
    line = 1
    length = len(src)

    while i < length:
        c = src[i]

        # Whitespace
        if c in ' \t\r':
            i += 1
            continue
        if c == '\n':
            line += 1
            i += 1
            continue

        # Single-line comment
        if c == '/' and i + 1 < length and src[i+1] == '/':
            while i < length and src[i] != '\n':
                i += 1
            continue

        # String literal
        if c == '"':
            i += 1
            s = ''
            while i < length and src[i] != '"':
                s += src[i]
                i += 1
            if i >= length:
                raise SyntaxError(f'[Lexer] Unterminated string at line {line}')
            i += 1  # closing "
            tokens.append({'type': 'STRING', 'value': s, 'line': line})
            continue

        # Number
        if c.isdigit():
            v = ''
            has_dot = False
            while i < length and (src[i].isdigit() or src[i] == '.'):
                if src[i] == '.':
                    has_dot = True
                v += src[i]
                i += 1
            tokens.append({'type': 'FLOAT' if has_dot else 'INT', 'value': v, 'line': line})
            continue

        # Identifier or keyword
        if c.isalpha() or c == '_':
            v = ''
            while i < length and (src[i].isalnum() or src[i] == '_'):
                v += src[i]
                i += 1
            if v in ('true', 'false'):
                tokens.append({'type': 'BOOL', 'value': v, 'line': line})
            elif v in KEYWORDS:
                tokens.append({'type': 'KEYWORD', 'value': v, 'line': line})
            else:
                tokens.append({'type': 'IDENT', 'value': v, 'line': line})
            continue

        # Two-char operators
        two = src[i:i+2]
        if two in ('->', '==', '!=', '<=', '>=', '&&', '||'):
            tokens.append({'type': 'OP', 'value': two, 'line': line})
            i += 2
            continue

        # Single-char operators
        if c in '+-*/%':
            tokens.append({'type': 'OP', 'value': c, 'line': line})
            i += 1
            continue
        if c in '<>':
            tokens.append({'type': 'OP', 'value': c, 'line': line})
            i += 1
            continue
        if c == '=' and (i + 1 >= length or src[i+1] != '='):
            tokens.append({'type': 'ASSIGN', 'value': c, 'line': line})
            i += 1
            continue
        if c in '(){},;:':
            tokens.append({'type': 'PUNCT', 'value': c, 'line': line})
            i += 1
            continue

        raise SyntaxError(f"[Lexer] Unexpected character '{c}' at line {line}")

    tokens.append({'type': 'EOF', 'value': '', 'line': line})
    return tokens


# ─────────────────────────────────────────────
# PHASE 2: PARSER → AST
# ─────────────────────────────────────────────
class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos]

    def consume(self, type_=None, val=None):
        t = self.tokens[self.pos]
        if type_ and t['type'] != type_:
            raise SyntaxError(f"[Parser] Expected {type_}{' ('+val+')' if val else ''} but got '{t['value']}' ({t['type']}) at line {t['line']}")
        if val and t['value'] != val:
            raise SyntaxError(f"[Parser] Expected '{val}' but got '{t['value']}' at line {t['line']}")
        self.pos += 1
        return t

    def check(self, type_, val=None):
        t = self.peek()
        return t['type'] == type_ and (val is None or t['value'] == val)

    def parse_type(self):
        t = self.peek()
        if t['type'] == 'KEYWORD' and t['value'] in ('int','float','bool','string','void'):
            self.pos += 1
            return t['value']
        raise SyntaxError(f"[Parser] Expected type at line {t['line']}")

    def parse_params(self):
        params = []
        self.consume('PUNCT', '(')
        while not self.check('PUNCT', ')'):
            name = self.consume('IDENT')['value']
            self.consume('PUNCT', ':')
            type_ = self.parse_type()
            params.append({'name': name, 'type': type_})
            if self.check('PUNCT', ','):
                self.consume('PUNCT', ',')
        self.consume('PUNCT', ')')
        return params

    def parse_block(self):
        self.consume('PUNCT', '{')
        stmts = []
        while not self.check('PUNCT', '}'):
            stmts.append(self.parse_stmt())
        self.consume('PUNCT', '}')
        return {'type': 'Block', 'body': stmts}

    def parse_stmt(self):
        t = self.peek()
        if t['type'] == 'KEYWORD':
            if t['value'] == 'let':    return self.parse_let()
            if t['value'] == 'return': return self.parse_return()
            if t['value'] == 'if':     return self.parse_if()
            if t['value'] == 'while':  return self.parse_while()
            if t['value'] == 'print':
                self.pos += 1
                self.consume('PUNCT', '(')
                arg = self.parse_expr()
                self.consume('PUNCT', ')')
                self.consume('PUNCT', ';')
                return {'type': 'Print', 'arg': arg}
        expr = self.parse_expr()
        self.consume('PUNCT', ';')
        return {'type': 'ExprStmt', 'expr': expr}

    def parse_let(self):
        self.consume('KEYWORD', 'let')
        name = self.consume('IDENT')['value']
        self.consume('PUNCT', ':')
        var_type = self.parse_type()
        self.consume('ASSIGN', '=')
        init = self.parse_expr()
        self.consume('PUNCT', ';')
        return {'type': 'Let', 'name': name, 'varType': var_type, 'init': init}

    def parse_return(self):
        self.consume('KEYWORD', 'return')
        val = None
        if not self.check('PUNCT', ';'):
            val = self.parse_expr()
        self.consume('PUNCT', ';')
        return {'type': 'Return', 'val': val}

    def parse_if(self):
        self.consume('KEYWORD', 'if')
        cond = self.parse_expr()
        then = self.parse_block()
        alt = None
        if self.check('KEYWORD', 'else'):
            self.pos += 1
            alt = self.parse_block()
        return {'type': 'If', 'cond': cond, 'then': then, 'alt': alt}

    def parse_while(self):
        self.consume('KEYWORD', 'while')
        cond = self.parse_expr()
        body = self.parse_block()
        return {'type': 'While', 'cond': cond, 'body': body}

    def parse_expr(self): return self.parse_or()

    def parse_or(self):
        left = self.parse_and()
        while self.check('OP', '||'):
            self.pos += 1
            right = self.parse_and()
            left = {'type': 'BinOp', 'op': '||', 'left': left, 'right': right}
        return left

    def parse_and(self):
        left = self.parse_eq()
        while self.check('OP', '&&'):
            self.pos += 1
            right = self.parse_eq()
            left = {'type': 'BinOp', 'op': '&&', 'left': left, 'right': right}
        return left

    def parse_eq(self):
        left = self.parse_cmp()
        while self.check('OP', '==') or self.check('OP', '!='):
            op = self.tokens[self.pos]['value']; self.pos += 1
            right = self.parse_cmp()
            left = {'type': 'BinOp', 'op': op, 'left': left, 'right': right}
        return left

    def parse_cmp(self):
        left = self.parse_add()
        while self.peek()['type'] == 'OP' and self.peek()['value'] in ('<','>','<=','>='):
            op = self.tokens[self.pos]['value']; self.pos += 1
            right = self.parse_add()
            left = {'type': 'BinOp', 'op': op, 'left': left, 'right': right}
        return left

    def parse_add(self):
        left = self.parse_mul()
        while self.peek()['type'] == 'OP' and self.peek()['value'] in ('+','-'):
            op = self.tokens[self.pos]['value']; self.pos += 1
            right = self.parse_mul()
            left = {'type': 'BinOp', 'op': op, 'left': left, 'right': right}
        return left

    def parse_mul(self):
        left = self.parse_unary()
        while self.peek()['type'] == 'OP' and self.peek()['value'] in ('*','/','%'):
            op = self.tokens[self.pos]['value']; self.pos += 1
            right = self.parse_unary()
            left = {'type': 'BinOp', 'op': op, 'left': left, 'right': right}
        return left

    def parse_unary(self):
        if self.check('OP', '-'):
            self.pos += 1
            return {'type': 'Unary', 'op': '-', 'expr': self.parse_unary()}
        if self.check('OP', '!'):
            self.pos += 1
            return {'type': 'Unary', 'op': '!', 'expr': self.parse_unary()}
        return self.parse_primary()

    def parse_primary(self):
        t = self.peek()
        if t['type'] == 'INT':
            self.pos += 1
            return {'type': 'Literal', 'kind': 'int', 'value': int(t['value'])}
        if t['type'] == 'FLOAT':
            self.pos += 1
            return {'type': 'Literal', 'kind': 'float', 'value': float(t['value'])}
        if t['type'] == 'BOOL':
            self.pos += 1
            return {'type': 'Literal', 'kind': 'bool', 'value': t['value'] == 'true'}
        if t['type'] == 'STRING':
            self.pos += 1
            return {'type': 'Literal', 'kind': 'string', 'value': t['value']}
        if t['type'] == 'IDENT':
            name = t['value']; self.pos += 1
            if self.check('PUNCT', '('):
                self.pos += 1
                args = []
                while not self.check('PUNCT', ')'):
                    args.append(self.parse_expr())
                    if self.check('PUNCT', ','): self.pos += 1
                self.pos += 1
                return {'type': 'Call', 'callee': name, 'args': args}
            return {'type': 'Ident', 'name': name}
        if t['type'] == 'PUNCT' and t['value'] == '(':
            self.pos += 1
            e = self.parse_expr()
            self.consume('PUNCT', ')')
            return e
        raise SyntaxError(f"[Parser] Unexpected token '{t['value']}' ({t['type']}) at line {t['line']}")

    def parse_fn(self):
        self.consume('KEYWORD', 'fn')
        name = self.consume('IDENT')['value']
        params = self.parse_params()
        self.consume('OP', '->')
        ret_type = self.parse_type()
        body = self.parse_block()
        return {'type': 'Fn', 'name': name, 'params': params, 'retType': ret_type, 'body': body}

    def parse_program(self):
        program = {'type': 'Program', 'fns': []}
        while self.peek()['type'] != 'EOF':
            if self.check('KEYWORD', 'fn'):
                program['fns'].append(self.parse_fn())
            else:
                t = self.peek()
                raise SyntaxError(f"[Parser] Expected 'fn' at top level, got '{t['value']}'")
        return program


def parse(tokens):
    return Parser(tokens).parse_program()


# ─────────────────────────────────────────────
# PHASE 3: SEMANTIC ANALYSIS
# ─────────────────────────────────────────────
def analyze(ast):
    symbols = {}
    warnings = []

    for fn in ast['fns']:
        if fn['name'] in symbols:
            raise TypeError(f"[Semantic] Duplicate function '{fn['name']}'")
        symbols[fn['name']] = {
            'kind': 'fn',
            'params': fn['params'],
            'retType': fn['retType'],
            'locals': {}
        }

    def infer_expr(expr, scope):
        t = expr['type']
        if t == 'Literal':
            return expr['kind']
        if t == 'Ident':
            if expr['name'] in scope:
                return scope[expr['name']]
            raise TypeError(f"[Semantic] Undefined variable '{expr['name']}'")
        if t == 'BinOp':
            lt = infer_expr(expr['left'], scope)
            rt = infer_expr(expr['right'], scope)
            cmp_ops = {'==','!=','<','>','<=','>=','&&','||'}
            if expr['op'] in cmp_ops:
                return 'bool'
            if lt != rt:
                raise TypeError(f"[Semantic] Type mismatch in '{expr['op']}': {lt} vs {rt}")
            return lt
        if t == 'Unary':
            ut = infer_expr(expr['expr'], scope)
            if expr['op'] == '-' and ut not in ('int','float'):
                raise TypeError(f"[Semantic] Unary '-' on non-numeric type")
            return ut
        if t == 'Call':
            fn = symbols.get(expr['callee'])
            if not fn:
                raise TypeError(f"[Semantic] Undefined function '{expr['callee']}'")
            if len(expr['args']) != len(fn['params']):
                raise TypeError(f"[Semantic] Wrong arg count for '{expr['callee']}'")
            for i, (arg, param) in enumerate(zip(expr['args'], fn['params'])):
                at = infer_expr(arg, scope)
                pt = param['type']
                if at != pt:
                    raise TypeError(f"[Semantic] Arg {i+1} of '{expr['callee']}': expected {pt} got {at}")
            return fn['retType']
        return 'void'

    def check_stmts(stmts, scope, fn_def):
        for s in stmts:
            st = s['type']
            if st == 'Let':
                it = infer_expr(s['init'], scope)
                if it != s['varType']:
                    raise TypeError(f"[Semantic] Cannot assign {it} to '{s['name']}:{s['varType']}'")
                if s['name'] in scope:
                    warnings.append(f"Variable '{s['name']}' shadows outer scope")
                scope[s['name']] = s['varType']
                fn_def['locals'][s['name']] = s['varType']
            elif st == 'Return':
                rt = infer_expr(s['val'], scope) if s['val'] else 'void'
                if rt != fn_def['retType']:
                    raise TypeError(f"[Semantic] Return type mismatch in '{fn_def['name']}': expected {fn_def['retType']} got {rt}")
            elif st == 'If':
                ct = infer_expr(s['cond'], scope)
                if ct != 'bool':
                    warnings.append(f"If condition is {ct}, expected bool")
                check_stmts(s['then']['body'], dict(scope), fn_def)
                if s['alt']:
                    check_stmts(s['alt']['body'], dict(scope), fn_def)
            elif st == 'While':
                check_stmts(s['body']['body'], dict(scope), fn_def)
            elif st == 'Print':
                infer_expr(s['arg'], scope)
            elif st == 'ExprStmt':
                infer_expr(s['expr'], scope)
            elif st == 'Block':
                check_stmts(s['body'], dict(scope), fn_def)

    for fn in ast['fns']:
        scope = {p['name']: p['type'] for p in fn['params']}
        check_stmts(fn['body']['body'], scope, symbols[fn['name']])

    return {'symbols': symbols, 'warnings': warnings}


# ─────────────────────────────────────────────
# PHASE 4: IR GENERATION (3-Address Code)
# ─────────────────────────────────────────────
def generate_ir(ast):
    instrs = []
    tmp_counter = [0]
    lbl_counter = [0]

    def new_tmp():
        t = f"t{tmp_counter[0]}"
        tmp_counter[0] += 1
        return t

    def new_lbl():
        l = f"L{lbl_counter[0]}"
        lbl_counter[0] += 1
        return l

    def emit(op, args=None, result=None, comment=''):
        instrs.append({'op': op, 'args': args or [], 'result': result, 'comment': comment})

    def emit_expr(expr):
        t = expr['type']
        if t == 'Literal':
            tmp = new_tmp()
            emit('CONST', [expr['value']], tmp, f"literal {expr['kind']}")
            return tmp
        if t == 'Ident':
            return expr['name']
        if t == 'BinOp':
            l = emit_expr(expr['left'])
            r = emit_expr(expr['right'])
            tmp = new_tmp()
            emit(expr['op'], [l, r], tmp)
            return tmp
        if t == 'Unary':
            v = emit_expr(expr['expr'])
            tmp = new_tmp()
            emit('NEG', [v], tmp)
            return tmp
        if t == 'Call':
            args = [emit_expr(a) for a in expr['args']]
            for a in args:
                emit('PARAM', [a], None, 'arg')
            tmp = new_tmp()
            emit('CALL', [expr['callee'], len(args)], tmp, f"call {expr['callee']}")
            return tmp
        return '_'

    def emit_stmts(stmts):
        for s in stmts:
            st = s['type']
            if st == 'Let':
                v = emit_expr(s['init'])
                emit('ASSIGN', [v], s['name'], f"let {s['name']}")
            elif st == 'Return':
                if s['val']:
                    v = emit_expr(s['val'])
                    emit('RETURN', [v])
                else:
                    emit('RETURN', [])
            elif st == 'If':
                cond = emit_expr(s['cond'])
                lbl_else = new_lbl()
                lbl_end = new_lbl()
                emit('IF_FALSE', [cond, lbl_else], None, 'if')
                emit_stmts(s['then']['body'])
                emit('GOTO', [lbl_end])
                emit('LABEL', [lbl_else])
                if s['alt']:
                    emit_stmts(s['alt']['body'])
                emit('LABEL', [lbl_end])
            elif st == 'While':
                lbl_start = new_lbl()
                lbl_end = new_lbl()
                emit('LABEL', [lbl_start], None, 'while')
                cond = emit_expr(s['cond'])
                emit('IF_FALSE', [cond, lbl_end])
                emit_stmts(s['body']['body'])
                emit('GOTO', [lbl_start])
                emit('LABEL', [lbl_end])
            elif st == 'Print':
                v = emit_expr(s['arg'])
                emit('PRINT', [v])
            elif st == 'ExprStmt':
                emit_expr(s['expr'])
            elif st == 'Block':
                emit_stmts(s['body'])

    for fn in ast['fns']:
        emit('FUNC_BEGIN', [fn['name']], None, f"fn {fn['name']}")
        for p in fn['params']:
            emit('PARAM_DECL', [p['name'], p['type']], None, 'param')
        emit_stmts(fn['body']['body'])
        emit('FUNC_END', [fn['name']])

    return instrs


# ─────────────────────────────────────────────
# PHASE 5: OPTIMIZER (Constant Folding + DCE)
# ─────────────────────────────────────────────
def optimize(ir):
    opts = []
    consts = {}
    used = set()

    for ins in ir:
        for a in ins['args']:
            if isinstance(a, str) and not a.startswith('L'):
                used.add(a)
        if ins['result'] and ins['op'] in ('PRINT','RETURN','PARAM','FUNC_BEGIN','FUNC_END'):
            used.add(ins['result'])

    result = []
    arith_ops = {'+', '-', '*', '/', '%'}
    cmp_ops   = {'==', '!=', '<', '>', '<=', '>='}

    for ins in ir:
        op = ins['op']

        if op == 'CONST':
            consts[ins['result']] = ins['args'][0]
            result.append({**ins, 'folded': False})
            continue

        if op in arith_ops | cmp_ops:
            a, b = ins['args'][0], ins['args'][1]
            cv_a = consts.get(a)
            cv_b = consts.get(b)
            if cv_a is not None and cv_b is not None:
                if   op == '+':  val = cv_a + cv_b
                elif op == '-':  val = cv_a - cv_b
                elif op == '*':  val = cv_a * cv_b
                elif op == '/':  val = cv_a / cv_b if cv_b != 0 else 0
                elif op == '%':  val = cv_a % cv_b if cv_b != 0 else 0
                elif op == '==': val = cv_a == cv_b
                elif op == '!=': val = cv_a != cv_b
                elif op == '<':  val = cv_a < cv_b
                elif op == '>':  val = cv_a > cv_b
                elif op == '<=': val = cv_a <= cv_b
                elif op == '>=': val = cv_a >= cv_b
                consts[ins['result']] = val
                result.append({'op':'CONST','args':[val],'result':ins['result'],
                               'comment':f"folded: {cv_a}{op}{cv_b}",'folded':True})
                opts.append({'kind':'Constant Folding',
                             'from': f"{a} {op} {b}",
                             'to': str(val),
                             'reg': ins['result']})
                continue

        if op in ('CONST','ASSIGN') and ins['result'] and \
           ins['result'].startswith('t') and ins['result'] not in used:
            opts.append({'kind':'Dead Store Elim',
                         'from': f"{ins['result']} = {ins['args'][0]}",
                         'to': '(removed)',
                         'reg': ins['result']})
            continue

        result.append({**ins, 'folded': False})

    return {'optimized': result, 'opts': opts}


# ─────────────────────────────────────────────
# PHASE 6: CODE GENERATION (pseudo-x86 assembly)
# ─────────────────────────────────────────────
def codegen(ir):
    lines = []
    regs = {}
    reg_idx = [0]

    def loc(name):
        if name in regs:
            return regs[name]
        r = f"%r{reg_idx[0]}"
        reg_idx[0] += 1
        regs[name] = r
        return r

    lines.append({'kind':'comment','text':'; VOLT Compiled Output — x86-64 pseudo-assembly'})
    lines.append({'kind':'comment','text':'; Generated by VOLT Compiler v1.0 (Python Backend)'})
    lines.append({'kind':'blank'})
    lines.append({'kind':'directive','text':'.section .text'})
    lines.append({'kind':'directive','text':'.global _start'})
    lines.append({'kind':'blank'})

    arith_map = {'+':'addq','-':'subq','*':'imulq','/':'idivq'}
    jmp_map   = {'==':'je','!=':'jne','<':'jl','>':'jg','<=':'jle','>=':'jge'}

    for ins in ir:
        op = ins['op']
        args = ins['args']
        res = ins['result']

        if op == 'FUNC_BEGIN':
            lines.append({'kind':'blank'})
            lines.append({'kind':'label','text':f"{args[0]}:"})
            lines.append({'kind':'instr','op':'pushq','args':'%rbp','comment':'save frame pointer'})
            lines.append({'kind':'instr','op':'movq','args':'%rsp, %rbp','comment':'set up stack frame'})
        elif op == 'FUNC_END':
            lines.append({'kind':'instr','op':'popq','args':'%rbp'})
            lines.append({'kind':'instr','op':'ret','args':'','comment':f"return from {args[0]}"})
        elif op == 'PARAM_DECL':
            lines.append({'kind':'comment','text':f"; param {args[0]}: {args[1]}"})
        elif op == 'CONST':
            v = 1 if args[0] is True else (0 if args[0] is False else args[0])
            regs[res] = '%rax'
            lines.append({'kind':'instr','op':'movq','args':f"${json.dumps(v)}, {loc(res)}",'comment':ins.get('comment','')})
        elif op == 'ASSIGN':
            src = regs.get(args[0], f"[{args[0]}]")
            lines.append({'kind':'instr','op':'movq','args':f"{src}, [{res}]",'comment':f"{res} = {args[0]}"})
            regs[res] = f"[{res}]"
        elif op in arith_map:
            a = regs.get(args[0], f"[{args[0]}]")
            b = regs.get(args[1], f"[{args[1]}]")
            lines.append({'kind':'instr','op':'movq','args':f"{a}, %rax"})
            lines.append({'kind':'instr','op':arith_map[op],'args':b,'comment':f"{args[0]} {op} {args[1]}"})
            lines.append({'kind':'instr','op':'movq','args':f"%rax, [{res}]"})
            regs[res] = f"[{res}]"
        elif op in jmp_map:
            a = regs.get(args[0], f"[{args[0]}]")
            b = regs.get(args[1], f"[{args[1]}]")
            set_op = 'set' + jmp_map[op][1:]
            lines.append({'kind':'instr','op':'cmpq','args':f"{b}, {a}",'comment':f"compare for {op}"})
            lines.append({'kind':'instr','op':set_op,'args':'%al'})
            lines.append({'kind':'instr','op':'movzbq','args':f"%al, [{res}]"})
            regs[res] = f"[{res}]"
        elif op == 'IF_FALSE':
            cond = regs.get(args[0], f"[{args[0]}]")
            lines.append({'kind':'instr','op':'cmpq','args':f"$0, {cond}"})
            lines.append({'kind':'instr','op':'je','args':args[1],'comment':'branch if false'})
        elif op == 'GOTO':
            lines.append({'kind':'instr','op':'jmp','args':args[0]})
        elif op == 'LABEL':
            lines.append({'kind':'label','text':f"{args[0]}:"})
        elif op == 'PARAM':
            v = regs.get(args[0], f"[{args[0]}]")
            lines.append({'kind':'instr','op':'pushq','args':v,'comment':'push arg'})
        elif op == 'CALL':
            lines.append({'kind':'instr','op':'call','args':args[0],'comment':f"call {args[0]}"})
            lines.append({'kind':'instr','op':'movq','args':f"%rax, [{res}]"})
            regs[res] = f"[{res}]"
        elif op == 'RETURN':
            if args:
                v = regs.get(args[0], f"[{args[0]}]")
                lines.append({'kind':'instr','op':'movq','args':f"{v}, %rax",'comment':'return value'})
        elif op == 'PRINT':
            v = regs.get(args[0], f"[{args[0]}]")
            lines.append({'kind':'instr','op':'movq','args':f"{v}, %rdi",'comment':'print arg'})
            lines.append({'kind':'instr','op':'call','args':'volt_print'})
        elif op == 'NEG':
            v = regs.get(args[0], f"[{args[0]}]")
            lines.append({'kind':'instr','op':'movq','args':f"{v}, %rax"})
            lines.append({'kind':'instr','op':'negq','args':'%rax'})
            lines.append({'kind':'instr','op':'movq','args':f"%rax, [{res}]"})
            regs[res] = f"[{res}]"

    return lines


# ─────────────────────────────────────────────
# MAIN COMPILE FUNCTION
# ─────────────────────────────────────────────
def compile_volt(src: str) -> dict:
    """
    Run all 6 compiler phases and return structured results.
    Each phase returns its output or an error dict.
    """
    result = {}

    try:
        tokens = lex(src)
        result['lexer'] = {
            'success': True,
            'tokens': tokens,
            'count': len([t for t in tokens if t['type'] != 'EOF'])
        }
    except Exception as e:
        result['lexer'] = {'success': False, 'error': str(e)}
        return result

    try:
        ast = parse(tokens)
        result['parser'] = {
            'success': True,
            'ast': ast,
            'fn_count': len(ast['fns'])
        }
    except Exception as e:
        result['parser'] = {'success': False, 'error': str(e)}
        return result

    try:
        sem = analyze(ast)
        result['semantic'] = {
            'success': True,
            'symbols': sem['symbols'],
            'warnings': sem['warnings'],
            'symbol_count': len(sem['symbols'])
        }
    except Exception as e:
        result['semantic'] = {'success': False, 'error': str(e)}
        return result

    try:
        ir = generate_ir(ast)
        result['ir'] = {
            'success': True,
            'instructions': ir,
            'count': len(ir)
        }
    except Exception as e:
        result['ir'] = {'success': False, 'error': str(e)}
        return result

    try:
        opt = optimize(ir)
        result['optimizer'] = {
            'success': True,
            'optimized': opt['optimized'],
            'opts': opt['opts'],
            'count': len(opt['opts'])
        }
    except Exception as e:
        result['optimizer'] = {'success': False, 'error': str(e)}
        return result

    try:
        asm = codegen(opt['optimized'])
        result['codegen'] = {
            'success': True,
            'assembly': asm,
            'instr_count': len([l for l in asm if l['kind'] == 'instr'])
        }
    except Exception as e:
        result['codegen'] = {'success': False, 'error': str(e)}
        return result

    return result


# ─────────────────────────────────────────────
# PYDANTIC MODELS
# ─────────────────────────────────────────────
class CompileRequest(BaseModel):
    source: str


# ─────────────────────────────────────────────
# FASTAPI ROUTES
# ─────────────────────────────────────────────
@app.get("/")
def index():
    return {
        "name": "VOLT Compiler API",
        "version": "1.0.0",
        "description": "6-phase compiler: Lexer → Parser → Semantic → IR Gen → Optimizer → Code Gen",
        "endpoints": {
            "POST /compile": "Run all 6 phases on source code",
            "POST /compile/lexer": "Run lexer phase only",
            "POST /compile/parser": "Run lexer + parser phases",
            "POST /compile/semantic": "Run up to semantic analysis",
            "POST /compile/ir": "Run up to IR generation",
            "POST /compile/optimizer": "Run up to optimizer",
            "GET /health": "Health check",
        }
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/compile")
def compile_all(body: CompileRequest):
    """Run all 6 compiler phases."""
    result = compile_volt(body.source)
    return result


@app.post("/compile/lexer")
def compile_lexer(body: CompileRequest):
    """Run lexer phase only."""
    try:
        tokens = lex(body.source)
        return {
            "success": True,
            "tokens": tokens,
            "count": len([t for t in tokens if t['type'] != 'EOF'])
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/compile/parser")
def compile_parser(body: CompileRequest):
    """Run lexer + parser phases."""
    try:
        tokens = lex(body.source)
        ast = parse(tokens)
        return {
            "success": True,
            "ast": ast,
            "fn_count": len(ast['fns'])
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/compile/semantic")
def compile_semantic(body: CompileRequest):
    """Run up to semantic analysis."""
    try:
        tokens = lex(body.source)
        ast = parse(tokens)
        sem = analyze(ast)
        return {
            "success": True,
            "symbols": sem['symbols'],
            "warnings": sem['warnings'],
            "symbol_count": len(sem['symbols'])
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/compile/ir")
def compile_ir(body: CompileRequest):
    """Run up to IR generation."""
    try:
        tokens = lex(body.source)
        ast = parse(tokens)
        analyze(ast)
        ir = generate_ir(ast)
        return {
            "success": True,
            "instructions": ir,
            "count": len(ir)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/compile/optimizer")
def compile_optimizer(body: CompileRequest):
    """Run up to optimizer."""
    try:
        tokens = lex(body.source)
        ast = parse(tokens)
        analyze(ast)
        ir = generate_ir(ast)
        opt = optimize(ir)
        return {
            "success": True,
            "optimized": opt['optimized'],
            "opts": opt['opts'],
            "count": len(opt['opts'])
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─────────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────────
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)