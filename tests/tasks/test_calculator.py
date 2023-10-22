import unittest
from .shared import TaskTestBase
from streamtasks.tasks.calculator import CalculatorGrammar, CalculatorEvalContext, CalculatorEvalTransformer
import math


class TestCalculator(TaskTestBase):
  def test_lang(self):
    res = CalculatorGrammar.parse("sin(a)+b")
    transformer = CalculatorEvalTransformer(CalculatorEvalContext({
      "a": 1,
      "b": 2
    }))

    self.assertEqual(transformer.transform(res), math.sin(1) + 2)


if __name__ == '__main__':
  unittest.main()