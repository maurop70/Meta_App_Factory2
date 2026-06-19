# Meta App Factory Architectural Standards
# Version: 1.0.0 (V3 Hardened)
# Authority: Maintenance V3 Core Deployment

## 1. Explicit Relationship Mapping (MANDATORY)
To prevent `PGRST201` (ambiguous join) errors in Supabase/Postgrest, ALL queries that embed related tables MUST explicitly define the foreign key relationship.

### Correct Syntax
```python
# Explicitly name the FK column after the table name with an exclamation mark
supabase.table("work_orders").select("*, departments!department_ref_id(*)")
supabase.table("app_users").select("*, roles!role_id(*)")
```

### Forbidden Syntax
```python
# Ambiguous - will fail if multiple FKs exist between tables
supabase.table("work_orders").select("*, departments(*)")
```

## 2. Role Identity Normalization
Personnel must be linked to roles via `role_id` (UUID). Text-based role lookups are deprecated.

## 3. Native Event Dispatching
High-priority alerts must use the `app_notifications` SQL ledger for persistence and auditability. Avoid external dependencies (e.g., n8n) for core state-change notifications.

## 4. Work Order Traceability
Every status change must be logged to `work_order_history` with the `user_id` and a mandatory `note`.

## 5. Deterministic Regression Suites (MANDATORY)
Regression suites must be deterministic and offline-capable. They MUST NOT depend on a live LLM call to pass — model output is non-deterministic and bills credits on every run.

- To test a self-healing / generative **loop**, exercise the mechanical piping (detect → re-actuate → re-verify) by substituting a **known-good** artifact for the model's output. Do not assert that the LLM produced a correct fix.
- Heavyweight or environment-dependent checks (real browsers, dev-server boots, network) belong in a **gated** stage (e.g. `RUN_FULLSTACK_E2E=1`) that is skipped by default, so the always-on suite stays fast and hermetic.
- New features get **new** suites — never mutate the assertions/counts of an existing suite.
- Reference implementation: `Master_Architect_Elite_Logic/test_fullstack_healing.py`.

## 6. Server-Side Document Ingestion (MANDATORY)
Uploaded documents (PDF / DOCX / PPTX / CSV / …) MUST be turned into clean text **server-side** before reaching any LLM. Reading a binary file as raw UTF-8 (`open(path, "r", encoding="utf-8")`) feeds binary noise to the model and produces generic, document-blind output.

- Use the single shared parser, `document_parser_service.DocumentParserService`, for all extraction. New formats are added there (extension in `SUPPORTED_EXTENSIONS` + a `_extract_<fmt>` handler), never reimplemented per call site.
- Gate on capability before parsing: `parser.is_supported(path)` → `parser._extract_text(path, ext)`; treat an `"ERROR:"`-prefixed return as a failure and fall back deliberately (raw read, or staging an image to the multimodal API).
- Only **images** belong on the Google File API (`genai.upload_file`). Text-bearing binaries must be inlined as extracted text so that sub-agents without File-API access (CMO/CFO/CIO) actually see the content.
- Keep the upload allow-lists in sync: a format accepted by an ingest router (`backend/app/routers/ingest.py`) must be supported by the parser.
