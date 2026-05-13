"""
数据校验工具
用于校验各阶段输出的数据格式
"""

from ..core.document_parser import ProblemSpec


def validate_problem_spec(spec: ProblemSpec) -> tuple[bool, list[str]]:
    """
    校验 ProblemSpec 是否完整

    Args:
        spec: 题目规格说明

    Returns:
        (是否有效, 错误信息列表)
    """
    errors = []

    if not spec.title:
        errors.append("缺少题目标题")
    if not spec.description:
        errors.append("缺少问题描述")
    if not spec.problem_type:
        errors.append("缺少问题类型")

    return len(errors) == 0, errors
