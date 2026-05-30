from pydantic import BaseModel
from typing import List

class CIOIntelligenceSchema(BaseModel):
    """
    Strict CIO intelligence extraction schema.
    Guarantees air-gapped schema validation prior to vectorization.
    """
    core_concepts: List[str]
    market_signals: List[str]
    threat_vectors: List[str]
