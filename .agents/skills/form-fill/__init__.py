"""form-fill skill — fill PDF/Word forms from any data source, deriving values as needed."""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "data-context"))

from form_fill import (detect_form, extract_nl_facts, fill_simple_form, fill_matrix_form,
                       fill_pdf_acroform, fill_docx, fill_docx_matrix, overlay_text_pdf,
                       detect_grid_anchors_pdf, read_pdf_fields, read_docx_table_grid, FillReport)
from data_context import DataContext, reconcile_matrix, match_category

__all__ = ["detect_form", "extract_nl_facts", "fill_simple_form", "fill_matrix_form",
           "fill_pdf_acroform", "fill_docx", "fill_docx_matrix", "overlay_text_pdf",
           "detect_grid_anchors_pdf", "read_pdf_fields", "read_docx_table_grid", "FillReport",
           "DataContext", "reconcile_matrix", "match_category"]
