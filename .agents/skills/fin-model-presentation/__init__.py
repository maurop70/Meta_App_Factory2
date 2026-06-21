"""fin-model-presentation skill — make a fin-model boardroom-ready (charts, cover, PDF)."""
try:
    from .fin_model_presentation import (present, add_native_charts, build_board_pdf,
                                         apply_print_setup)
    from .brand_tokens import load_tokens, BrandTokens
    from .qa import qa_pdf, render_pages
except ImportError:
    from fin_model_presentation import (present, add_native_charts, build_board_pdf,
                                        apply_print_setup)
    from brand_tokens import load_tokens, BrandTokens
    from qa import qa_pdf, render_pages

__all__ = ["present", "add_native_charts", "build_board_pdf", "apply_print_setup",
           "load_tokens", "BrandTokens", "qa_pdf", "render_pages"]
