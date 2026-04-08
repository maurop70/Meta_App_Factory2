import io
import pandas as pd
from cfo_logic import FinancialPayload, CMOPayload, ArchitectRiskPayload

def extract_financials_from_file(file_bytes: bytes, filename: str) -> FinancialPayload:
    """
    Reads an uploaded .xlsx or .csv file using pandas.
    Extracts key metrics: cash on hand, mrr/revenue, opex/expenses, liabilities/debt.
    Raises ValueError if a required metric is missing.
    """
    filename_lower = filename.lower()
    try:
        if filename_lower.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(file_bytes))
        elif filename_lower.endswith('.xlsx') or filename_lower.endswith('.xls'):
            df = pd.read_excel(io.BytesIO(file_bytes))
        else:
            raise ValueError("Unsupported file format. Please upload .csv or .xlsx")
    except Exception as e:
        raise ValueError(f"Failed to parse file '{filename}': {str(e)}")

    # Flatten dataframe into a long string representation per row to hunt for keywords
    # This allows flexibility regardless of whether it's two columns [Metric, Value] or wide.
    # A robust approach: find the row containing the keyword, then find the first parsable float in that row.
    metrics_found = {
        "cash_on_hand": None,
        "mrr": None,
        "opex": None,
        "liabilities": None
    }

    # Helper maps for hunting
    aliases = {
        "cash_on_hand": ["cash", "cash on hand", "liquidity", "bank"],
        "mrr": ["revenue", "mrr", "arr", "income", "sales"],
        "opex": ["expenses", "opex", "operating expenses", "burn"],
        "liabilities": ["liabilities", "debt", "loans", "payables"]
    }

    def extract_first_number(row_series):
        for val in row_series.values:
            if isinstance(val, (int, float)) and not pd.isna(val):
                return float(val)
            # Try to convert string to float (remove $ and commas)
            if isinstance(val, str):
                cleaned = str(val).replace('$', '').replace(',', '').strip()
                try:
                    return float(cleaned)
                except ValueError:
                    continue
        return None

    # Search logic: iter rows, stringify cells, hunt for match
    for idx, row in df.iterrows():
        row_str = " ".join([str(v).lower() for v in row.values if not pd.isna(v)])
        
        for key, possible_names in aliases.items():
            if metrics_found[key] is None:
                # If any alias is in the row string (simple substring match)
                if any(alias in row_str for alias in possible_names):
                    val = extract_first_number(row)
                    if val is not None:
                        metrics_found[key] = val

    # Validation
    missing_metrics = [k for k, v in metrics_found.items() if v is None]
    if missing_metrics:
        raise ValueError(f"Missing required financial data in file. Could not locate: {', '.join(missing_metrics)}")

    return FinancialPayload(
        cmo_spend=CMOPayload(total=50000.0, allocated=48000.0, categories={}),
        architect_risk=ArchitectRiskPayload(structural_score=70.0, logic_score=70.0, security_score=70.0, composite_score=70.0),
        campaign_list=[],
        cash_on_hand=metrics_found["cash_on_hand"],
        mrr=metrics_found["mrr"],
        opex=metrics_found["opex"],
        liabilities=metrics_found["liabilities"]
    )
