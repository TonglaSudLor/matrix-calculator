import unittest

from calculator import CalculatorError, calculate


class CalculatorTests(unittest.TestCase):
    def test_matrix_workflow_and_ans(self):
        a = calculate('RotZ = [[cos(theta1), -sin(theta1)], [sin(theta1), cos(theta1)]]')
        b = calculate('B = [l1 0; 0 d1]')
        product = calculate('C = alpha * RotZ * B', {'RotZ': a, 'B': b})
        self.assertEqual(product['kind'], 'matrix')
        self.assertIn('alpha', product['cells'][0][0])
        self.assertIn('theta_1', product['cells'][0][0])
        self.assertEqual(calculate('trace(ans)', {'ans': product})['kind'], 'scalar')

    def test_matrix_operations(self):
        a = calculate('A = [[1, 2], [3, 4]]')
        names = {'A': a}
        self.assertEqual(calculate('det(A)', names)['text'], '-2')
        self.assertEqual(calculate("A'", names)['cells'], [['1', '3'], ['2', '4']])
        self.assertEqual(calculate('A^-1', names)['cells'], [['-2', '1'], ['3/2', '-1/2']])
        self.assertEqual(calculate('rref(A)', names)['cells'], [['1', '0'], ['0', '1']])
        self.assertEqual(calculate('A^2', names)['cells'], [['7', '10'], ['15', '22']])
        self.assertEqual(calculate('A * I(2)', names)['cells'], a['cells'])
        self.assertEqual(calculate('i(3)')['cells'], [['1', '0', '0'], ['0', '1', '0'], ['0', '0', '1']])

    def test_rectangular_and_nested(self):
        result = calculate('transpose([[1,2,3],[4,5,6]]) * [[1],[2]]')
        self.assertEqual(result['cells'], [['9'], ['12'], ['15']])
        self.assertEqual(calculate('det([[1,2],[3,4]] * I(2))')['text'], '-2')

    def test_symbolic_conditions_and_simplify(self):
        inverse = calculate('inverse([[theta,0],[0,1]])')
        self.assertTrue(inverse['conditions'])
        self.assertIn('theta', inverse['conditions'][0]['text'])
        self.assertTrue(calculate('det(B)', {'B': inverse})['conditions'])
        reduced = calculate('rref([[theta,0],[0,1]])')
        self.assertTrue(reduced['conditions'])
        self.assertEqual(calculate('simplify(sin(theta)^2 + cos(theta)^2)')['text'], '1')
        self.assertNotEqual(calculate('sin(theta)^2 + cos(theta)^2')['text'], '1')

    def test_numbers_and_pi(self):
        self.assertEqual(calculate('1/3')['text'], '1/3')
        self.assertEqual(calculate('toPi(1.57079632679)')['text'], 'pi/2')
        self.assertIn('0.333', calculate('decimal(1/3)')['text'])
        self.assertEqual(calculate('2theta1')['text'], '2*theta_1')
        self.assertEqual(calculate('2θ₁')['text'], '2*theta_1')

    def test_angle_setting_and_steps(self):
        degrees = calculate('2cos(30)', angle_unit='DEG')
        self.assertEqual(degrees['text'], 'sqrt(3)')
        self.assertEqual(len(degrees['steps']), 2)
        self.assertNotEqual(calculate('2cos(30)', angle_unit='RAD')['text'], degrees['text'])
        self.assertEqual(calculate('cos(theta)', angle_unit='DEG')['text'], 'cos(theta)')
        with self.assertRaises(CalculatorError):
            calculate('cos(30)', angle_unit='GRAD')

    def test_trig_shorthand(self):
        self.assertEqual(calculate('cosl1')['text'], calculate('cos(l1)')['text'])
        self.assertEqual(calculate('sintheta')['text'], calculate('sin(theta)')['text'])
        self.assertEqual(calculate('tan30')['text'], calculate('tan(30)')['text'])
        self.assertEqual(calculate('2cos30')['text'], 'sqrt(3)')
        self.assertEqual(calculate('sinθ₁')['text'], calculate('sin(theta1)')['text'])

    def test_assign_symbol_values(self):
        result = calculate('[[cos(theta), l1], [0, d1]]', angle_unit='DEG',
                           symbol_values={'theta': '60', 'l_1': '2', 'd_1': '3'})
        self.assertEqual(result['cells'], [['1/2', '2'], ['0', '3']])
        self.assertEqual(result['symbols'], ['d_1', 'l_1', 'theta'])
        self.assertEqual(result['symbolic']['cells'][0][0], 'cos(theta)')
        partial = calculate('l1 + d1', symbol_values={'l_1': '2'})
        self.assertEqual(partial['text'], 'd_1 + 2')
        stored = calculate('A', {'A': result['symbolic']}, symbol_values={'theta': '60', 'l_1': '2', 'd_1': '3'})
        self.assertEqual(stored['cells'], result['cells'])
        self.assertEqual(calculate('cos(theta)', angle_unit='RAD', symbol_values={'theta': 'pi'})['text'], '-1')
        degrees_pi = calculate('cos(theta)', angle_unit='DEG', symbol_values={'theta': 'pi'})['text']
        self.assertAlmostEqual(float(degrees_pi), 0.998497149864, places=10)
        with self.assertRaises(CalculatorError):
            calculate('l1', symbol_values={'l_1': 'theta'})

    def test_errors(self):
        with self.assertRaises(CalculatorError):
            calculate('A/B', {'A': calculate('I(2)'), 'B': calculate('I(2)')})
        with self.assertRaises(CalculatorError):
            calculate('rank(I(2))')
        with self.assertRaises(CalculatorError):
            calculate('inverse([[1,0],[0,0]])')
        with self.assertRaises(CalculatorError):
            calculate('__import__("os")')


if __name__ == '__main__':
    unittest.main()
