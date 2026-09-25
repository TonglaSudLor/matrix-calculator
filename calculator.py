"""Restricted symbolic matrix calculator used by the local web app."""

import ast
import re
from fractions import Fraction

import sympy as sp
from sympy.matrices.exceptions import NonInvertibleMatrixError


GREEK = {
    'α': 'alpha', 'β': 'beta', 'γ': 'gamma', 'δ': 'delta', 'θ': 'theta',
    'λ': 'lambda', 'μ': 'mu', 'π': 'pi', 'φ': 'phi', 'ω': 'omega',
}
SUBSCRIPT = str.maketrans('₀₁₂₃₄₅₆₇₈₉', '0123456789')
FUNCTIONS = {'sin': sp.sin, 'cos': sp.cos, 'tan': sp.tan, 'sqrt': sp.sqrt}
RESERVED = {'ans', 'I', 'i', 'pi', 'transpose', 'det', 'inverse', 'trace', 'rref', 'simplify', 'decimal', 'toPi', *FUNCTIONS}
MAX_SIZE = 4


class CalculatorError(ValueError):
    pass


def is_matrix(value):
    return isinstance(value, sp.MatrixBase)


def normalize_source(source):
    source = source.strip()
    if not source or len(source) > 3000:
        raise CalculatorError('สูตรว่างหรือยาวเกินไป')
    source = re.sub(r'([A-Za-zα-ω])([₀-₉]+)', lambda m: m[1] + '_' + m[2].translate(SUBSCRIPT), source)
    for glyph, name in GREEK.items():
        source = source.replace(glyph, name)
    source = re.sub(
        r'(?<![A-Za-z_])(?:sin|cos|tan)(?:[A-Za-z_][A-Za-z_0-9]*|\d+(?:\.\d+)?)',
        lambda match: re.match(r'(sin|cos|tan)(.+)', match[0]).expand(r'\1(\2)'),
        source,
    )
    source = re.sub(r"\b([A-Za-z_][A-Za-z_0-9]*)'", r'transpose(\1)', source)
    source = re.sub(r'(?<![A-Za-z_])(\d+(?:\.\d+)?)(?=[A-Za-z_])', r'\1*', source)
    source = source.replace('^', '**')
    source = normalize_matlab_matrices(source)
    return source


def normalize_matlab_matrices(source):
    # Convert [1 2; 3 4] to [[1,2],[3,4]]. Nested list syntax stays intact.
    pairs = []
    stack = []
    for index, char in enumerate(source):
        if char == '[':
            stack.append(index)
        elif char == ']':
            if not stack:
                raise CalculatorError('วงเล็บเมทริกซ์ไม่ครบ')
            pairs.append((stack.pop(), index))
    if stack:
        raise CalculatorError('วงเล็บเมทริกซ์ไม่ครบ')
    for start, end in sorted(pairs, reverse=True):
        body = source[start + 1:end]
        if ';' not in body or '[' in body:
            continue
        rows = []
        for row in body.split(';'):
            entries = re.split(r'\s+', row.strip())
            if not entries or not all(entries):
                raise CalculatorError('แถวเมทริกซ์ว่าง')
            rows.append('[' + ','.join(entries) + ']')
        source = source[:start] + '[' + ','.join(rows) + ']' + source[end + 1:]
    return source


def symbol_name(name):
    match = re.fullmatch(r'([a-z]+)_?(\d+)', name)
    return f'{match[1]}_{match[2]}' if match else name


class Evaluator:
    def __init__(self, names=None, angle_unit='DEG'):
        self.names = names or {}
        self.angle_unit = angle_unit
        self.conditions = []
        self.name_conditions = {}
        self.inherited_conditions = []
        self.steps = []

    def record_binary(self, op, left, right, result):
        if is_matrix(left) or is_matrix(right) or getattr(result, 'free_symbols', set()):
            return
        symbols = {'+': '+', '-': '-', '*': r'\cdot', '/': r'\div', '^': '^'}
        if op in symbols:
            self.steps.append({'latex': f'{sp.latex(left)} {symbols[op]} {sp.latex(right)} = {sp.latex(result)}'})

    def require_nonzero(self, expression):
        expression = sp.factor(expression)
        if expression.is_zero is True:
            raise CalculatorError('เมทริกซ์เป็นเอกฐานหรือตัวหารเป็นศูนย์')
        if expression.is_zero is None:
            condition = sp.Ne(expression, 0, evaluate=False)
            if condition not in self.conditions:
                self.conditions.append(condition)

    def parse(self, source):
        try:
            tree = ast.parse(normalize_source(source), mode='eval')
        except (SyntaxError, ValueError) as error:
            raise CalculatorError('รูปแบบสูตรไม่ถูกต้อง') from error
        return self.visit(tree.body)

    def visit(self, node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return sp.Rational(str(node.value))
        if isinstance(node, ast.Name):
            if node.id in self.names:
                for condition in self.name_conditions.get(node.id, []):
                    if condition not in self.inherited_conditions:
                        self.inherited_conditions.append(condition)
                return self.names[node.id]
            if node.id == 'pi':
                return sp.pi
            if node.id in {'ans', 'I', 'i'}:
                raise CalculatorError(f'ยังไม่มีค่า {node.id}')
            return sp.Symbol(symbol_name(node.id), real=True)
        if isinstance(node, ast.List):
            if node.elts and all(isinstance(item, ast.List) for item in node.elts):
                entries = [[self.visit(cell) for cell in row.elts] for row in node.elts]
                widths = {len(row) for row in entries}
                if len(widths) != 1 or not 1 <= len(entries) <= MAX_SIZE or not 1 <= len(entries[0]) <= MAX_SIZE:
                    raise CalculatorError('เมทริกซ์ต้องมี 1–4 แถวและคอลัมน์เท่ากันทุกแถว')
                if any(is_matrix(cell) or isinstance(cell, list) for row in entries for cell in row):
                    raise CalculatorError('ช่องเมทริกซ์ต้องเป็นนิพจน์หนึ่งค่า')
                return sp.Matrix(entries)
            entries = [self.visit(item) for item in node.elts]
            if not 1 <= len(entries) <= MAX_SIZE or any(is_matrix(item) or isinstance(item, list) for item in entries):
                raise CalculatorError('เวกเตอร์ต้องมี 1–4 ค่า')
            return sp.Matrix(entries)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = self.visit(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp):
            left, right = self.visit(node.left), self.visit(node.right)
            try:
                if isinstance(node.op, ast.Add):
                    result = left + right
                    self.record_binary('+', left, right, result)
                    return result
                if isinstance(node.op, ast.Sub):
                    result = left - right
                    self.record_binary('-', left, right, result)
                    return result
                if isinstance(node.op, ast.Mult):
                    result = left * right
                    self.record_binary('*', left, right, result)
                    return result
                if isinstance(node.op, ast.Div):
                    if is_matrix(left) or is_matrix(right):
                        raise CalculatorError('ใช้ inverse(B) แทนการหารเมทริกซ์')
                    self.require_nonzero(right)
                    result = left / right
                    self.record_binary('/', left, right, result)
                    return result
                if isinstance(node.op, ast.Pow):
                    if is_matrix(left):
                        if not right.is_Integer:
                            raise CalculatorError('กำลังของเมทริกซ์ต้องเป็นจำนวนเต็ม')
                        if right < 0:
                            self.require_nonzero(left.det())
                        return left ** int(right)
                    result = left ** right
                    self.record_binary('^', left, right, result)
                    return result
            except (sp.ShapeError, NonInvertibleMatrixError, TypeError, ValueError, ZeroDivisionError) as error:
                raise CalculatorError('ขนาดเมทริกซ์ไม่ตรงกัน หรือคำนวณสูตรนี้ไม่ได้') from error
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            name = node.func.id
            args = [self.visit(arg) for arg in node.args]
            if len(args) != 1:
                raise CalculatorError(f'{name} ต้องมีอาร์กิวเมนต์หนึ่งค่า')
            value = args[0]
            if name in {'I', 'i'}:
                if not value.is_Integer or not 1 <= value <= MAX_SIZE:
                    raise CalculatorError('I(n) รองรับขนาด 1–4')
                return sp.eye(int(value))
            if name in FUNCTIONS:
                if is_matrix(value):
                    raise CalculatorError(f'{name} ใช้กับค่าในช่องเมทริกซ์')
                if name in {'sin', 'cos', 'tan'} and not value.free_symbols:
                    angle = value * sp.pi / 180 if self.angle_unit == 'DEG' else value
                    exact = FUNCTIONS[name](angle)
                    result = exact.evalf(12) if exact.has(sp.sin, sp.cos, sp.tan) else exact
                    unit = r'^{\circ}' if self.angle_unit == 'DEG' else ''
                    self.steps.append({'latex': f'\\{name}\\left({sp.latex(value)}{unit}\\right) = {sp.latex(result)}'})
                    return result
                return FUNCTIONS[name](value)
            if name in {'transpose', 'det', 'inverse', 'trace', 'rref'}:
                if not is_matrix(value):
                    raise CalculatorError(f'{name} ต้องใช้กับเมทริกซ์')
                if name == 'transpose':
                    return value.T
                if name == 'det':
                    if value.rows != value.cols:
                        raise CalculatorError('det ใช้กับเมทริกซ์จัตุรัส')
                    return value.det()
                if name == 'trace':
                    if value.rows != value.cols:
                        raise CalculatorError('trace ใช้กับเมทริกซ์จัตุรัส')
                    return sp.trace(value)
                if name == 'inverse':
                    if value.rows != value.cols:
                        raise CalculatorError('inverse ใช้กับเมทริกซ์จัตุรัส')
                    self.require_nonzero(value.det())
                    return value.inv()
                return self.rref(value)
            if name == 'simplify':
                operation = lambda item: sp.trigsimp(sp.simplify(item))
                return value.applyfunc(operation) if is_matrix(value) else operation(value)
            if name == 'decimal':
                operation = lambda item: item.evalf(12)
                return value.applyfunc(operation) if is_matrix(value) else operation(value)
            if name == 'toPi':
                return value.applyfunc(self.to_pi) if is_matrix(value) else self.to_pi(value)
        raise CalculatorError('สูตรมีคำสั่งที่ไม่รองรับ')

    def rref(self, value):
        matrix = value.copy()
        pivot_row = 0
        for column in range(matrix.cols):
            candidates = [row for row in range(pivot_row, matrix.rows) if sp.cancel(matrix[row, column]).is_zero is not True]
            if not candidates:
                continue
            definite = [row for row in candidates if sp.cancel(matrix[row, column]).is_zero is False]
            row = definite[0] if definite else candidates[0]
            matrix.row_swap(pivot_row, row)
            pivot = sp.cancel(matrix[pivot_row, column])
            self.require_nonzero(pivot)
            matrix.row_op(pivot_row, lambda item, _: sp.cancel(item / pivot))
            for other in range(matrix.rows):
                if other == pivot_row:
                    continue
                factor = matrix[other, column]
                matrix.row_op(other, lambda item, col: sp.cancel(item - factor * matrix[pivot_row, col]))
            pivot_row += 1
            if pivot_row == matrix.rows:
                break
        return matrix

    def to_pi(self, value):
        if value == 0:
            return sp.Integer(0)
        if value.free_symbols:
            raise CalculatorError('toPi ใช้กับค่าตัวเลขหรือมุมที่รู้ค่าแล้ว')
        ratio = float(sp.N(value / sp.pi, 15))
        fraction = Fraction(ratio).limit_denominator(24)
        if abs(ratio - float(fraction)) > 1e-8:
            raise CalculatorError('ค่านี้ไม่ใช่สัดส่วนอย่างง่ายของ pi')
        return sp.Rational(fraction.numerator, fraction.denominator) * sp.pi


def serialize(value):
    if is_matrix(value):
        return {'kind': 'matrix', 'cells': [[sp.sstr(value[row, col]) for col in range(value.cols)] for row in range(value.rows)],
                'latex': sp.latex(value)}
    return {'kind': 'scalar', 'text': sp.sstr(value), 'latex': sp.latex(value)}


def calculate(formula, variables=None, angle_unit='DEG', symbol_values=None):
    variables = variables or {}
    symbol_values = symbol_values or {}
    if not isinstance(formula, str) or not isinstance(variables, dict) or len(variables) > 40:
        raise CalculatorError('ข้อมูลสูตรไม่ถูกต้อง')
    if not isinstance(symbol_values, dict) or len(symbol_values) > 40:
        raise CalculatorError('ข้อมูลค่าตัวแปรไม่ถูกต้อง')
    if angle_unit not in {'DEG', 'RAD'}:
        raise CalculatorError('หน่วยมุมต้องเป็น DEG หรือ RAD')
    evaluator = Evaluator(angle_unit=angle_unit)
    for name, data in variables.items():
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name) or (name in RESERVED and name != 'ans'):
            raise CalculatorError('ชื่อตัวแปรที่บันทึกไม่ถูกต้อง')
        if data.get('kind') == 'matrix':
            cells = data.get('cells')
            if not isinstance(cells, list) or not cells:
                raise CalculatorError('ข้อมูลเมทริกซ์ไม่ถูกต้อง')
            evaluator.names[name] = sp.Matrix([[Evaluator().parse(str(cell)) for cell in row] for row in cells])
        elif data.get('kind') == 'scalar':
            evaluator.names[name] = Evaluator().parse(str(data.get('text', '')))
        else:
            raise CalculatorError('ค่าที่บันทึกไม่ถูกต้อง')
        evaluator.name_conditions[name] = data.get('conditions', [])
    assignment = re.match(r'^\s*([A-Za-z][A-Za-z0-9_]*)\s*=\s*(.+)$', formula, re.S)
    name = assignment[1] if assignment else None
    if name in RESERVED:
        raise CalculatorError('ชื่อนี้สงวนไว้สำหรับคำสั่ง')
    expression = assignment[2] if assignment else formula
    value = evaluator.parse(expression)
    symbolic = serialize(value)
    symbols = sorted(str(symbol) for symbol in value.free_symbols)
    substitutions = {}
    for raw_name, raw_value in symbol_values.items():
        if not isinstance(raw_name, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', raw_name):
            raise CalculatorError('ชื่อตัวแปรไม่ถูกต้อง')
        if not isinstance(raw_value, str) or len(raw_value) > 100:
            raise CalculatorError('ค่าตัวแปรไม่ถูกต้อง')
        parsed = Evaluator(angle_unit=angle_unit).parse(raw_value)
        if is_matrix(parsed) or parsed.free_symbols:
            raise CalculatorError('ค่าตัวแปรต้องเป็นตัวเลขที่คำนวณได้')
        substitutions[sp.Symbol(symbol_name(raw_name), real=True)] = parsed
    if substitutions:
        def replace_trig(item):
            if angle_unit == 'DEG':
                item = item.replace(
                    lambda part: part.func in (sp.sin, sp.cos, sp.tan) and bool(part.free_symbols & substitutions.keys()),
                    lambda part: part.func(part.args[0] * sp.pi / 180),
                )
            item = sp.trigsimp(sp.simplify(item.subs(substitutions)))
            if not item.free_symbols and item.has(sp.sin, sp.cos, sp.tan):
                return item.evalf(12)
            return item
        value = value.applyfunc(replace_trig) if is_matrix(value) else replace_trig(value)
        for symbol in sorted(substitutions, key=str):
            if str(symbol) in symbols:
                evaluator.steps.append({'latex': f'{sp.latex(symbol)} = {sp.latex(substitutions[symbol])}'})
        evaluator.steps.append({'latex': f'{symbolic["latex"]} = {sp.latex(value)}'})
    result = serialize(value)
    result['assignment'] = name
    result['symbols'] = symbols
    result['symbolic'] = symbolic
    result['steps'] = evaluator.steps
    result['angleUnit'] = angle_unit
    result['conditions'] = list(evaluator.inherited_conditions)
    for condition in evaluator.conditions:
        rendered = {'text': sp.sstr(condition), 'latex': sp.latex(condition)}
        if rendered not in result['conditions']:
            result['conditions'].append(rendered)
    return result
