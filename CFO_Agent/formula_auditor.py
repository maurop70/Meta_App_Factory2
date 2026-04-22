"""
formula_auditor.py — Specialized CFO Financial Engineering Tool
══════════════════════════════════════════════════════════════
CIO Discovery #4: Deepen Specialized CFO Capabilities.
Provides a Pydantic-validated engine for generating and auditing
complex Excel formulas for financial modeling.
"""

import re
import logging
from typing import List, Optional, Dict
from pydantic import BaseModel, Field, validator

logger = logging.getLogger("FormulaAuditor")

class ExcelFormula(BaseModel):
    raw_formula: str = Field(..., description="The full Excel formula string starting with '='")
    cells_referenced: List[str] = Field(default_factory=list, description="List of cells like A1, B2:C10 referenced.")
    complexity_score: int = Field(0, ge=0, le=100, description="Estimated computational complexity.")
    is_volatile: bool = Field(False, description="True if formula uses volatile functions like OFFSET or INDIRECT.")

    @validator("raw_formula")
    def must_start_with_equals(cls, v):
        if not v.startswith("="):
            raise ValueError("Excel formulas must start with '='")
        return v

class FormulaAuditResult(BaseModel):
    formula: str
    is_valid: bool
    errors: List[str] = []
    recommendations: List[str] = []
    risk_level: str = "Low"  # Low, Medium, High

class CFOFormulaAuditor:
    def __init__(self):
        # Volatile functions in Excel
        self.volatile_funcs = ["OFFSET", "INDIRECT", "TODAY", "NOW", "RAND", "RANDBETWEEN", "INFO", "CELL"]

    def audit_formula(self, formula: str) -> FormulaAuditResult:
        """
        Audits an Excel formula for syntax, logic errors, and risks.
        """
        errors = []
        recommendations = []
        risk_level = "Low"

        # Basic Syntax Check
        if not formula.startswith("="):
            errors.append("Formula does not start with '='.")
        
        # Parentheses Matching
        if formula.count("(") != formula.count(")"):
            errors.append("Unmatched parentheses detected.")
            risk_level = "High"

        # Volatile Function Check
        found_volatile = [f for f in self.volatile_funcs if f in formula.upper()]
        if found_volatile:
            recommendations.append(f"Formula uses volatile functions: {', '.join(found_volatile)}. This may slow down large workbooks.")
            risk_level = "Medium"

        # Circular Reference Check (Simple Heuristic)
        # In a real tool, we'd need the target cell context, but we can flag potential self-references if provided.

        return FormulaAuditResult(
            formula=formula,
            is_valid=len(errors) == 0,
            errors=errors,
            recommendations=recommendations,
            risk_level=risk_level
        )

    def generate_formula(self, intent: str) -> ExcelFormula:
        """
        Mock implementation of formula generation. 
        In a production environment, this would call a fine-tuned LLM 
        specifically trained on financial Excel modeling.
        """
        # Example logic for standard financial intents
        formula = "=SUM(A1:A10)" # Default fallback
        cells = ["A1:A10"]
        
        if "vlookup" in intent.lower():
            formula = "=VLOOKUP(A1, B1:D100, 2, FALSE)"
            cells = ["A1", "B1:D100"]
        elif "irr" in intent.lower():
            formula = "=IRR(B1:B10)"
            cells = ["B1:B10"]
        
        return ExcelFormula(
            raw_formula=formula,
            cells_referenced=cells,
            complexity_score=30,
            is_volatile=False
        )

if __name__ == "__main__":
    auditor = CFOFormulaAuditor()
    test_f = "=VLOOKUP(A1, Sheet2!A1:B100, 2, FALSE" # Missing paren
    result = auditor.audit_formula(test_f)
    print(result.json(indent=2))
