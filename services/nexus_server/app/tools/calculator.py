import ast
import operator
from collections.abc import Callable
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from app.tools.base import PermissionLevel, Tool, ToolContext, ToolError

Number = int | float
BinaryOperation = Callable[[Number, Number], Number]


class CalculatorInput(BaseModel):
    expression: str = Field(min_length=1, max_length=200)


class CalculatorTool(Tool):
    name = "calculator"
    description = "Evaluate a basic arithmetic expression without executing code."
    permission_level = PermissionLevel.READ_ONLY
    input_schema = CalculatorInput

    _binary_operations: ClassVar[dict[type[ast.operator], BinaryOperation]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    _unary_operations: ClassVar[dict[type[ast.unaryop], Callable[[Number], Number]]] = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    async def execute(
        self,
        arguments: BaseModel,
        context: ToolContext,
    ) -> dict[str, Any]:
        del context
        parsed = CalculatorInput.model_validate(arguments)
        try:
            tree = ast.parse(parsed.expression, mode="eval")
            if sum(1 for _ in ast.walk(tree)) > 64:
                raise ValueError("expression is too complex")
            result = self._evaluate(tree.body)
        except (SyntaxError, TypeError, ValueError, ZeroDivisionError) as error:
            raise ToolError(
                "CALCULATOR_INVALID_EXPRESSION",
                "The arithmetic expression is invalid.",
                retryable=True,
            ) from error
        return {"expression": parsed.expression, "result": result}

    def _evaluate(self, node: ast.expr) -> Number:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, int | float):
                raise TypeError("only numbers are supported")
            return node.value
        if isinstance(node, ast.BinOp):
            binary_operation = self._binary_operations.get(type(node.op))
            if binary_operation is None:
                raise TypeError("operation is not supported")
            left = self._evaluate(node.left)
            right = self._evaluate(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 10:
                raise ValueError("exponent is too large")
            return binary_operation(left, right)
        if isinstance(node, ast.UnaryOp):
            unary_operation = self._unary_operations.get(type(node.op))
            if unary_operation is None:
                raise TypeError("operation is not supported")
            return unary_operation(self._evaluate(node.operand))
        raise TypeError("expression node is not supported")
