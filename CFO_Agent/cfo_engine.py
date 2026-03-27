"""
═══════════════════════════════════════════════════════════════
 Antigravity CFO Execution Controller
 Local execution engine for generating financial reports
 Called by N8N Python node or directly via API
═══════════════════════════════════════════════════════════════
"""
import json
import os
import io
from datetime import datetime

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.chart import BarChart, Reference
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


class CFOExecutionController:
    """
    CFO Agent Core: Transforms CMO spend data, Architect risk scores,
    and campaign lists into high-integrity financial models.
    """

    DISCOUNT_RATE = 0.10  # 10% default discount rate for NPV

    def __init__(self, output_dir=None):
        self.output_dir = output_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "reports"
        )
        os.makedirs(self.output_dir, exist_ok=True)

    # ── Gatekeeper ────────────────────────────────────────────
    def validate_payload(self, payload: dict) -> tuple:
        """
        The Gatekeeper: Validates that all required fields are present.
        Returns (is_valid, error_message).
        """
        required = ['cmo_spend', 'architect_risk', 'campaign_list']
        missing = [f for f in required if f not in payload]
        if missing:
            return False, (
                f"CFO Agent: Missing data from CMO or Architect. "
                f"Cannot calculate Fragility Index. Missing: {missing}"
            )
        return True, None

    # ── Core Financial Engine ─────────────────────────────────
    def calculate_fragility_index(self, architect_risk: dict) -> dict:
        """
        Fragility Index = 100 - Composite Score
        Higher fragility = more systemic vulnerability.
        """
        structural = architect_risk.get('structural_score', 70)
        logic = architect_risk.get('logic_score', 70)
        security = architect_risk.get('security_score', 70)
        composite = architect_risk.get('composite_score',
                                       round((structural * 0.4 + logic * 0.3 + security * 0.3), 1))

        return {
            'structural_score': structural,
            'logic_score': logic,
            'security_score': security,
            'composite': composite,
            'fragility_index': round(100 - composite, 1),
        }

    def analyze_campaigns(self, campaign_list: list, fragility: dict) -> list:
        """
        Per-campaign ROI, NPV, and risk-adjusted returns.
        NPV formula: PV = Revenue / (1 + r) - Cost
        Risk-adjusted ROI = ROI × (composite / 100)
        """
        results = []
        for campaign in campaign_list:
            spend = float(campaign.get('budget', 0))
            revenue = float(campaign.get('projected_revenue', 0))

            roi = round(((revenue - spend) / spend) * 100, 2) if spend > 0 else 0
            npv = round(revenue / (1 + self.DISCOUNT_RATE) - spend, 2)
            risk_adj_roi = round(roi * (fragility['composite'] / 100), 2)

            results.append({
                'name': campaign.get('name', 'Unknown'),
                'budget': spend,
                'projected_revenue': revenue,
                'roi_pct': roi,
                'npv': npv,
                'risk_adjusted_roi': risk_adj_roi,
                'irr_note': 'Single-period IRR = ROI%' if spend > 0 else 'N/A',
            })
        return results

    def reconcile_spend(self, cmo_spend: dict) -> dict:
        """CMO spend reconciliation: total vs allocated vs unallocated."""
        total = float(cmo_spend.get('total', 0))
        allocated = float(cmo_spend.get('allocated', 0))
        return {
            'total_budget': total,
            'allocated': allocated,
            'unallocated': round(total - allocated, 2),
            'utilization_pct': round((allocated / total) * 100, 2) if total > 0 else 0,
            'categories': cmo_spend.get('categories', {}),
        }

    # ── Report Generator ──────────────────────────────────────
    def generate_report(self, payload: dict) -> dict:
        """
        Full execution pipeline:
        1. Validate → 2. Calculate → 3. Build Schema → 4. Generate Excel
        """
        # 1. Validate
        valid, error = self.validate_payload(payload)
        if not valid:
            return {'error': True, 'message': error, 'status': 400}

        # 2. Calculate
        fragility = self.calculate_fragility_index(payload['architect_risk'])
        campaigns = self.analyze_campaigns(payload['campaign_list'], fragility)
        spend = self.reconcile_spend(payload['cmo_spend'])

        total_spend = sum(c['budget'] for c in campaigns)
        total_revenue = sum(c['projected_revenue'] for c in campaigns)
        portfolio_roi = round(((total_revenue - total_spend) / total_spend) * 100, 2) if total_spend > 0 else 0

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"CFO_Fragility_Report_{timestamp}.xlsx"

        # 3. Build Schema
        report = {
            'report_name': filename,
            'generated_at': datetime.now().isoformat(),
            'agent': 'CFO Execution Controller',

            'schema': {
                'tabs': [
                    {'name': 'Dashboard', 'purpose': 'Executive summary with Fragility Index, total ROI, and spend utilization'},
                    {'name': 'Calculation Engine', 'purpose': 'All NPV, IRR, ROI formulas with cell references'},
                    {'name': 'Input Data', 'purpose': 'Raw CMO spend, Architect risk scores, and campaign list'},
                    {'name': 'Campaign Analysis', 'purpose': 'Per-campaign ROI, NPV, and risk-adjusted returns'},
                ]
            },

            'formula_map': {
                'Dashboard!B2': '=100-Input_Data!B12  // Fragility Index',
                'Dashboard!B4': '=SUM(Campaign_Analysis!D:D)  // Total Spend',
                'Dashboard!B6': '=SUM(Campaign_Analysis!E:E)  // Total Revenue',
                'Dashboard!B8': '=((B6-B4)/B4)*100  // Portfolio ROI %',
                'Dashboard!B10': '=(Input_Data!B4/Input_Data!B3)*100  // Spend Utilization %',
                'Calculation_Engine!C2': '=E2/(1+$B$1)-D2  // NPV per campaign',
                'Calculation_Engine!F2': '=((E2-D2)/D2)*100  // ROI % per campaign',
                'Calculation_Engine!G2': '=F2*(Input_Data!B12/100)  // Risk-Adj ROI',
            },

            'logic_rationale': (
                'The Fragility Index is derived as the inverse of the Architect composite score '
                '(100 - composite), representing systemic vulnerability. Campaign ROI uses standard '
                'return-on-investment: ((Revenue - Cost) / Cost × 100). NPV applies a 10% discount '
                'rate for single-period projection. Risk-adjusted ROI multiplies raw ROI by the '
                'normalized composite score to penalize returns in fragile environments.'
            ),

            'fragility': fragility,
            'spend_reconciliation': spend,
            'campaigns': campaigns,
            'summary': {
                'fragility_index': fragility['fragility_index'],
                'total_spend': total_spend,
                'total_projected_revenue': total_revenue,
                'portfolio_roi_pct': portfolio_roi,
                'campaign_count': len(campaigns),
                'spend_utilization_pct': spend['utilization_pct'],
            },
        }

        # 4. Generate Excel file
        filepath = None
        if EXCEL_AVAILABLE:
            filepath = self._build_excel(report, filename)
            report['file_path'] = filepath

        report['file_name'] = filename
        report['status'] = 'ready_for_upload'
        return report

    # ── Excel Builder ─────────────────────────────────────────
    def _build_excel(self, report: dict, filename: str) -> str:
        """Generates the actual .xlsx with 4 tabs."""
        wb = openpyxl.Workbook()

        # Styles
        header_font = Font(name='Calibri', bold=True, size=12, color='FFFFFF')
        header_fill = PatternFill(start_color='1A1A2E', end_color='1A1A2E', fill_type='solid')
        value_font = Font(name='Calibri', size=11)
        currency_fmt = '#,##0.00'
        pct_fmt = '0.00"%"'
        thin_border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin'),
        )

        def style_header(ws, row, cols):
            for col in range(1, cols + 1):
                cell = ws.cell(row=row, column=col)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal='center')
                cell.border = thin_border

        # ── Tab 1: Dashboard ──────────────────────────────────
        ws = wb.active
        ws.title = 'Dashboard'
        ws.column_dimensions['A'].width = 30
        ws.column_dimensions['B'].width = 25

        dash_data = [
            ('CFO FRAGILITY REPORT', ''),
            ('Generated', report['generated_at']),
            ('', ''),
            ('FRAGILITY INDEX', report['fragility']['fragility_index']),
            ('Composite Score', report['fragility']['composite']),
            ('', ''),
            ('PORTFOLIO SUMMARY', ''),
            ('Total Spend', report['summary']['total_spend']),
            ('Total Projected Revenue', report['summary']['total_projected_revenue']),
            ('Portfolio ROI %', report['summary']['portfolio_roi_pct']),
            ('Campaign Count', report['summary']['campaign_count']),
            ('', ''),
            ('SPEND UTILIZATION', ''),
            ('Budget Utilization %', report['spend_reconciliation']['utilization_pct']),
            ('Allocated', report['spend_reconciliation']['allocated']),
            ('Unallocated', report['spend_reconciliation']['unallocated']),
        ]
        for r, (label, value) in enumerate(dash_data, 1):
            ws.cell(row=r, column=1, value=label).font = Font(bold=True, size=11)
            cell = ws.cell(row=r, column=2, value=value)
            cell.font = value_font
            if isinstance(value, (int, float)) and 'Spend' in label or 'Revenue' in label or 'Allocated' in label:
                cell.number_format = currency_fmt

        # Title styling
        ws['A1'].font = Font(name='Calibri', bold=True, size=16, color='E94560')

        # ── Tab 2: Calculation Engine ─────────────────────────
        ws2 = wb.create_sheet('Calculation Engine')
        ws2.column_dimensions['A'].width = 20
        ws2.column_dimensions['B'].width = 45
        ws2.column_dimensions['C'].width = 15

        ws2.cell(row=1, column=1, value='FORMULA MAP').font = Font(bold=True, size=14, color='E94560')
        ws2.cell(row=2, column=1, value='Discount Rate').font = Font(bold=True)
        ws2.cell(row=2, column=2, value=self.DISCOUNT_RATE)
        ws2.cell(row=2, column=2).number_format = '0.00%'

        ws2.cell(row=4, column=1, value='Cell Reference')
        ws2.cell(row=4, column=2, value='Formula / Logic')
        ws2.cell(row=4, column=3, value='Value')
        style_header(ws2, 4, 3)

        row = 5
        for cell_ref, formula in report['formula_map'].items():
            ws2.cell(row=row, column=1, value=cell_ref).font = Font(name='Consolas', size=10)
            ws2.cell(row=row, column=2, value=formula).font = value_font
            row += 1

        row += 1
        ws2.cell(row=row, column=1, value='LOGIC RATIONALE').font = Font(bold=True, size=12, color='E94560')
        ws2.cell(row=row + 1, column=1, value=report['logic_rationale']).font = Font(size=10, italic=True)

        # ── Tab 3: Input Data ─────────────────────────────────
        ws3 = wb.create_sheet('Input Data')
        ws3.column_dimensions['A'].width = 25
        ws3.column_dimensions['B'].width = 20

        ws3.cell(row=1, column=1, value='CMO SPEND DATA').font = Font(bold=True, size=14, color='E94560')
        input_rows = [
            ('Total Budget', report['spend_reconciliation']['total_budget']),
            ('Allocated', report['spend_reconciliation']['allocated']),
            ('Unallocated', report['spend_reconciliation']['unallocated']),
            ('Utilization %', report['spend_reconciliation']['utilization_pct']),
        ]
        for r, (k, v) in enumerate(input_rows, 3):
            ws3.cell(row=r, column=1, value=k).font = Font(bold=True)
            ws3.cell(row=r, column=2, value=v)

        ws3.cell(row=8, column=1, value='ARCHITECT RISK SCORES').font = Font(bold=True, size=14, color='E94560')
        risk_rows = [
            ('Structural Score', report['fragility']['structural_score']),
            ('Logic Score', report['fragility']['logic_score']),
            ('Security Score', report['fragility']['security_score']),
            ('Composite Score', report['fragility']['composite']),
            ('Fragility Index', report['fragility']['fragility_index']),
        ]
        for r, (k, v) in enumerate(risk_rows, 9):
            ws3.cell(row=r, column=1, value=k).font = Font(bold=True)
            ws3.cell(row=r, column=2, value=v)

        # ── Tab 4: Campaign Analysis ──────────────────────────
        ws4 = wb.create_sheet('Campaign Analysis')
        headers = ['Campaign', 'Budget', 'Projected Revenue', 'ROI %', 'NPV', 'Risk-Adj ROI %']
        for c, h in enumerate(headers, 1):
            ws4.cell(row=1, column=c, value=h)
            ws4.column_dimensions[chr(64 + c)].width = 20
        style_header(ws4, 1, len(headers))

        for r, camp in enumerate(report['campaigns'], 2):
            ws4.cell(row=r, column=1, value=camp['name'])
            ws4.cell(row=r, column=2, value=camp['budget']).number_format = currency_fmt
            ws4.cell(row=r, column=3, value=camp['projected_revenue']).number_format = currency_fmt
            ws4.cell(row=r, column=4, value=camp['roi_pct']).number_format = '0.00'
            ws4.cell(row=r, column=5, value=camp['npv']).number_format = currency_fmt
            ws4.cell(row=r, column=6, value=camp['risk_adjusted_roi']).number_format = '0.00'

        # Save
        filepath = os.path.join(self.output_dir, filename)
        wb.save(filepath)
        return filepath


# ═══════════════════════════════════════════════════════════════
# Standalone test
# ═══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    test_payload = {
        "cmo_spend": {
            "total": 50000,
            "allocated": 42000,
            "categories": {"digital_ads": 20000, "content": 12000, "events": 10000}
        },
        "architect_risk": {
            "structural_score": 82,
            "logic_score": 78,
            "security_score": 85,
            "composite_score": 81.6
        },
        "campaign_list": [
            {"name": "Q2 Product Launch", "budget": 15000, "projected_revenue": 45000},
            {"name": "Brand Awareness", "budget": 12000, "projected_revenue": 18000},
            {"name": "Retention Program", "budget": 8000, "projected_revenue": 24000},
        ]
    }

    cfo = CFOExecutionController()
    result = cfo.generate_report(test_payload)

    print(json.dumps(result, indent=2, default=str))
    if result.get('file_path'):
        print(f"\n📊 Excel report saved to: {result['file_path']}")
