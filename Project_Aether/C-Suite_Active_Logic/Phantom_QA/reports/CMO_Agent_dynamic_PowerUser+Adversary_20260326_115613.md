# Phantom QA Report — CMO_Agent
**Persona:** dynamic_PowerUser+Adversary
**Date:** 2026-03-26 11:56:13
**Pass Rate:** 50% (9/18)

| # | Test | Status | Details | Duration |
|---|---|---|---|---|
| 1 | Root Endpoint Probe | ✅ PASS | HTTP 200 | 2096ms |
| 2 | Health Check (/api/health) | ✅ PASS | HTTP 200 | 2052ms |
| 3 | OpenAPI: GET / | ✅ PASS | HTTP 200 | 2045ms |
| 4 | OpenAPI: GET /api/health | ✅ PASS | HTTP 200 | 2047ms |
| 5 | OpenAPI: GET /api/dashboard | ✅ PASS | HTTP 200 | 2055ms |
| 6 | OpenAPI: POST /api/market-research | ❌ FAIL | HTTP 500 | 2102ms |
| 7 | OpenAPI: POST /api/brand-studio | ❌ FAIL | HTTP 500 | 2047ms |
| 8 | OpenAPI: POST /api/gtm-plan | ❌ FAIL | HTTP 500 | 2048ms |
| 9 | OpenAPI: POST /api/personas | ❌ FAIL | HTTP 500 | 2043ms |
| 10 | OpenAPI: POST /api/campaigns | ❌ FAIL | HTTP 500 | 2058ms |
| 11 | OpenAPI: POST /api/competitive-analysis | ❌ FAIL | HTTP 500 | 2051ms |
| 12 | OpenAPI: GET /api/memory/brand/{project_name} | ✅ PASS | HTTP 200 | 2049ms |
| 13 | [PowerUser] Root endpoint | ✅ PASS | HTTP 200 | 2044ms |
| 14 | [PowerUser] Health check | ✅ PASS | HTTP 200 | 2058ms |
| 15 | [PowerUser] Status endpoint | ❌ FAIL | HTTP 404 | 2036ms |
| 16 | [Adversary] Root access | ✅ PASS | HTTP 200 | 2069ms |
| 17 | [Adversary] POST to GET endpoint | ❌ FAIL | HTTP 405 | 2065ms |
| 18 | [Adversary] 404 handling | ❌ FAIL | HTTP 404 | 2083ms |

## Failures
- **OpenAPI: POST /api/market-research**: HTTP 500
- **OpenAPI: POST /api/brand-studio**: HTTP 500
- **OpenAPI: POST /api/gtm-plan**: HTTP 500
- **OpenAPI: POST /api/personas**: HTTP 500
- **OpenAPI: POST /api/campaigns**: HTTP 500
- **OpenAPI: POST /api/competitive-analysis**: HTTP 500
- **[PowerUser] Status endpoint**: HTTP 404
- **[Adversary] POST to GET endpoint**: HTTP 405
- **[Adversary] 404 handling**: HTTP 404