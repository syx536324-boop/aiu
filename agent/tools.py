"""智能体工具分发模块：执行安全计算及受限的知识文件操作。"""

from __future__ import annotations

import ast
import math
import operator
from typing import Any

from agent.knowledge import (
    Confirmation,
    create_knowledge_file,
    delete_knowledge_file,
    list_knowledge_files,
    read_knowledge_file,
    replace_knowledge_file,
)

_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_UNARY_OPERATORS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
MAX_EXPRESSION_LENGTH = 100
MAX_AST_NODES = 30
MAX_ABS_RESULT = 1_000_000_000_000
MAX_ABS_EXPONENT = 12


def calculator(expression: str) -> str:
    """计算安全子集内的算术表达式，不执行 Python 代码。"""
    if not isinstance(expression, str) or not expression.strip():
        return "计算失败：表达式不能为空。"
    if len(expression) > MAX_EXPRESSION_LENGTH:
        return "计算失败：表达式太长。"

    try:
        tree = ast.parse(expression, mode="eval")
        if sum(1 for _ in ast.walk(tree)) > MAX_AST_NODES:
            return "计算失败：表达式太复杂。"
        value = _evaluate(tree.body)
    except ZeroDivisionError:
        return "计算失败：不能除以零。"
    except (SyntaxError, TypeError, ValueError, KeyError, OverflowError) as exc:
        return f"计算失败：只支持基础四则运算和有限次乘方（{exc}）。"

    if (isinstance(value, float) and not math.isfinite(value)) or abs(value) > MAX_ABS_RESULT:
        return "计算失败：结果超出允许范围。"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)


def execute_tool(
    name: str, arguments: dict[str, Any], confirm: Confirmation | None = None
) -> str:
    """根据允许列表分派工具调用，不运行模型提供的任意代码。"""
    if name == "calculator":
        expression = arguments.get("expression")
        if not isinstance(expression, str):
            return "计算失败：expression 参数必须是字符串。"
        return calculator(expression)
    if name == "list_knowledge_files":
        return list_knowledge_files()
    if name == "read_knowledge_file":
        filename = arguments.get("filename")
        if not isinstance(filename, str):
            return "读取失败：filename 参数必须是字符串。"
        return read_knowledge_file(filename)
    if name in {"create_knowledge_file", "replace_knowledge_file"}:
        filename = arguments.get("filename")
        content = arguments.get("content")
        if not isinstance(filename, str) or not isinstance(content, str):
            return "文件操作失败：filename 和 content 参数都必须是字符串。"
        if name == "create_knowledge_file":
            return create_knowledge_file(filename, content, confirm)
        return replace_knowledge_file(filename, content, confirm)
    if name == "delete_knowledge_file":
        filename = arguments.get("filename")
        if not isinstance(filename, str):
            return "文件操作失败：filename 参数必须是字符串。"
        return delete_knowledge_file(filename, confirm)
    return f"工具不存在：{name or '未命名工具'}。"


def _evaluate(node: ast.AST) -> int | float:
    """递归解释经过白名单限制的算术语法树。"""
    if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
        return _check_range(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        left = _evaluate(node.left)
        right = _evaluate(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_ABS_EXPONENT:
            raise ValueError(f"指数绝对值不能大于 {MAX_ABS_EXPONENT}")
        return _check_range(_BINARY_OPERATORS[type(node.op)](left, right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
        return _UNARY_OPERATORS[type(node.op)](_evaluate(node.operand))
    raise TypeError(f"不支持的语法：{type(node).__name__}")


def _check_range(value: int | float) -> int | float:
    """限制中间数值，避免超大数继续参与后续计算。"""
    if (isinstance(value, float) and not math.isfinite(value)) or abs(value) > MAX_ABS_RESULT:
        raise ValueError("数值超出允许范围")
    return value
