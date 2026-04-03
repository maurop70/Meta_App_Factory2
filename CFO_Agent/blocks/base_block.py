"""
Base Block
Defines the interface for all financial blocks in the CFO Compiler.
"""

class BaseBlock:
    def __init__(self, name: str, complexity: str, parameters: dict):
        self.name = name
        self.complexity = complexity  # 'elementary', 'mid_market', 'institutional'
        self.parameters = parameters
        self.cell_map = {}  # Stores generated cell references (e.g. {'revenue_y1': 'B2'})

    def render(self, ws, start_row: int, current_col: int = 1) -> int:
        """
        Renders the block onto the given openpyxl worksheet starting at start_row.
        Returns the next available row index.
        """
        raise NotImplementedError("Subclasses must implement render()")

    def get_references(self) -> dict:
        """
        Returns a dictionary of named cell references for cross-block linking.
        """
        return self.cell_map

    def _apply_pattern(self, formula: str, protect_math: bool = True) -> str:
        """
        Applies mathematical protection if requested (IFERROR wrapper).
        Sourced from cfo_patterns.json 'protect_math' logic.
        """
        if protect_math and formula.startswith("="):
            inner = formula[1:]
            return f"=IFERROR({inner}, 0)"
        return formula
