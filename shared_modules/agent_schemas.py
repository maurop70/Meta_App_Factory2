from pydantic import BaseModel, field_validator, model_validator
from typing import Optional
import logging

log = logging.getLogger("AgentSchemas")

class CFOOutput(BaseModel):
    status: str
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    total_cost: float = 0.0
    projected_revenue: float = 0.0
    roi_percentage: float = 0.0
    npv: float = 0.0
    irr_pct: float = 0.0
    breakeven_months: float = 0.0
    net_income_y1: float = 0.0

    @model_validator(mode='after')
    def validate_financials_not_zero(self):
        if self.status == "success":
            if self.projected_revenue == 0.0 and self.roi_percentage == 0.0:
                raise ValueError(
                    "[CFO SCHEMA VIOLATION] projected_revenue and "
                    "roi_percentage are both zero on a success status. "
                    "Financial model generation failed silently."
                )
        return self

class CIOOutput(BaseModel):
    status: str
    data: Optional[str] = None
    summary: Optional[str] = None
    results: Optional[list] = None

    @model_validator(mode='after')
    def validate_data_not_empty(self):
        if self.status == "success":
            has_data = (
                (self.data and len(self.data.strip()) > 50) or
                (self.summary and len(self.summary.strip()) > 50) or
                (self.results and len(self.results) > 0)
            )
            if not has_data:
                raise ValueError(
                    "[CIO SCHEMA VIOLATION] CIO returned success status "
                    "but all data fields are empty or too short. "
                    "Web crawl likely failed silently."
                )
        return self

class CriticOutput(BaseModel):
    score: float
    objections: list

    @field_validator('score')
    @classmethod
    def score_must_be_valid(cls, v):
        if v < 0 or v > 10:
            raise ValueError(f"[CRITIC SCHEMA VIOLATION] Score {v} out of range 0-10")
        return v

    @model_validator(mode='after')
    def validate_low_score_has_objections(self):
        if self.score < 7.0 and len(self.objections) == 0:
            raise ValueError(
                "[CRITIC SCHEMA VIOLATION] Score below 7.0 but no "
                "objections provided. Critic validation failed silently."
            )
        return self

def validate_cfo_output(raw: dict) -> CFOOutput:
    try:
        return CFOOutput(**raw)
    except Exception as e:
        log.error(f"[SCHEMA] CFO output validation failed: {e}")
        raise

def validate_cio_output(raw: dict) -> CIOOutput:
    try:
        return CIOOutput(**raw)
    except Exception as e:
        log.error(f"[SCHEMA] CIO output validation failed: {e}")
        raise

def validate_critic_output(raw: dict) -> CriticOutput:
    try:
        return CriticOutput(**raw)
    except Exception as e:
        log.error(f"[SCHEMA] Critic output validation failed: {e}")
        raise
