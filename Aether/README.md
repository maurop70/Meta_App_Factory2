# Aether — Creative Intelligence Engine

> Meta App Factory | Antigravity-AI

Aether is the creative intelligence layer powering presentations, financial reports, and design reasoning for the Antigravity-AI agent ecosystem.

## Modules

| Module | Description |
|:-------|:------------|
| `creative_director.py` | V3 Creative Director — design reasoning + orchestrator |
| `financial_architect.py` | Formula-driven XLSX with embedded charts |
| `presentation_architect.py` | AudienceSwitch PPTX with visual node maps |
| `executive_report_runner.py` | Report generation orchestrator |

## Features

### Creative Director V3
- **`design_reasoning()`**: Determines Visual Focus, Iconography, and Layout per slide
- Tries Gemini API first, falls back to built-in design library
- Generates `design_reasoning_log.json` with reasoning for every slide

### Financial Architect V2
- **Assumptions Tab**: Editable driver cells (agents, cost, revenue, growth)
- **100% Formula-Driven**: All P&L cells reference Assumptions (change one cell → everything updates)
- **Embedded Charts**: Line Chart (12-month growth) + Pie Chart (cost distribution)
- **Sensitivity Analysis**: Base, +25%, +50%, Doubled, Tripled, Revenue -20%
- **Agent Economics**: Per-agent cost, decisions, ROI contribution

### Presentation Architect V2
- **AudienceSwitch**: Investor (scalability + ROI) vs Customer (UX + safety)
- **Visual Node Map**: 5 color-coded clusters (System Core, Intelligence, Quality, Executive, Creative)
- **Sensitivity Analysis**: Investor-only slide (costs doubled scenario)
- **Dark-mode template**: 16:9, Inter/Roboto fonts, accent bar branding

## Usage

```bash
# Generate V3-Beautified report (Financial + Presentation + Reasoning)
python Aether/creative_director.py --run

# Test design reasoning only
python Aether/creative_director.py --test-reasoning

# Financial projections only
python Aether/financial_architect.py --test

# Presentation only
python Aether/presentation_architect.py --test --audience investor
python Aether/presentation_architect.py --test --audience customer
```

## Output

Reports are generated in `data/V3_Beautified/`:
- `Delegate_AI_V3_Projections.xlsx`
- `Delegate_AI_V3_Investor_Pitch.pptx`
- `design_reasoning_log.json`

## Security

- OAuth credentials loaded via `os.getenv()` — never hardcoded
- PIIMasker applied to all log output
- `utils/auth/` directory is gitignored
