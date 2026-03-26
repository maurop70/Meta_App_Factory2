# Phantom QA Report — CMO_Agent
**Persona:** dynamic_PowerUser+Adversary
**Date:** 2026-03-26 11:59:23
**Pass Rate:** 50% (9/18)

| # | Test | Status | Details | Duration |
|---|---|---|---|---|
| 1 | Root Endpoint Probe | ✅ PASS | HTTP 200 | 2081ms |
| 2 | Health Check (/api/health) | ✅ PASS | HTTP 200 | 2054ms |
| 3 | OpenAPI: GET / | ✅ PASS | HTTP 200 | 2073ms |
| 4 | OpenAPI: GET /api/health | ✅ PASS | HTTP 200 | 2050ms |
| 5 | OpenAPI: GET /api/dashboard | ✅ PASS | HTTP 200 | 2052ms |
| 6 | OpenAPI: POST /api/market-research | ❌ FAIL | HTTP 400 | 2036ms |
| 7 | OpenAPI: POST /api/brand-studio | ❌ FAIL | HTTP 400 | 2039ms |
| 8 | OpenAPI: POST /api/gtm-plan | ❌ FAIL | HTTP 400 | 2047ms |
| 9 | OpenAPI: POST /api/personas | ❌ FAIL | HTTP 400 | 2052ms |
| 10 | OpenAPI: POST /api/campaigns | ❌ FAIL | HTTP 400 | 2038ms |
| 11 | OpenAPI: POST /api/competitive-analysis | ❌ FAIL | HTTP 400 | 2063ms |
| 12 | OpenAPI: GET /api/memory/brand/{project_name} | ✅ PASS | HTTP 200 | 2060ms |
| 13 | [PowerUser] Root endpoint | ✅ PASS | HTTP 200 | 2056ms |
| 14 | [PowerUser] Health check | ✅ PASS | HTTP 200 | 2048ms |
| 15 | [PowerUser] Status endpoint | ❌ FAIL | HTTP 404 | 2043ms |
| 16 | [Adversary] Root access | ✅ PASS | HTTP 200 | 2053ms |
| 17 | [Adversary] POST to GET endpoint | ❌ FAIL | HTTP 405 | 2055ms |
| 18 | [Adversary] 404 handling | ❌ FAIL | HTTP 404 | 2040ms |

## Failures
- **OpenAPI: POST /api/market-research**: HTTP 400
- **OpenAPI: POST /api/brand-studio**: HTTP 400
- **OpenAPI: POST /api/gtm-plan**: HTTP 400
- **OpenAPI: POST /api/personas**: HTTP 400
- **OpenAPI: POST /api/campaigns**: HTTP 400
- **OpenAPI: POST /api/competitive-analysis**: HTTP 400
- **[PowerUser] Status endpoint**: HTTP 404
- **[Adversary] POST to GET endpoint**: HTTP 405
- **[Adversary] 404 handling**: HTTP 404