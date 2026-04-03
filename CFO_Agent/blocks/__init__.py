"""
CFO Agent Block Library
Modular components for generating scalable financial models.
"""

from .base_block import BaseBlock
from .revenue_block import RevenueBlock
from .debt_block import DebtBlock
from .returns_block import ReturnsBlock

__all__ = [
    'BaseBlock',
    'RevenueBlock',
    'DebtBlock',
    'ReturnsBlock'
]
