from auto_heal import healed_post, auto_heal, diagnose

"""
document_parser_service.py — Global Document Parsing Utility
═══════════════════════════════════════════════════════════════
Extracts text from documents (PDF, DOCX, TXT, CSV) and uses
Gemini AI to categorize them into business domains.

Part of the Meta_App_Factory V3 infrastructure.
Works alongside scribe.py (documentation GENERATOR) as the
document PARSER — complementary roles.

Usage:
    from document_parser_service import DocumentParserService
    parser = DocumentParserService()
    result = parser.parse("path/to/contract.pdf", source_app="Sentinel_Bridge")
"""

import os
import sys
import json
import uuid
import hashlib
import logging
from datetime import datetime
from typing import Optional

# ── V3 Resilience Integration ──────────────────────────
FACTORY_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, FACTORY_DIR)

try:
    from local_state_manager import StateManager
    _sm = StateManager()
except ImportError:
    _sm = None

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(FACTORY_DIR, ".env"))
except ImportError:
    pass

logger = logging.getLogger("DocumentParser")

# ── Supported categories ──────────────────────────────────
CATEGORIES = ["Legal", "Finance", "Ops", "Medical", "Technical", "Other"]

# ── Supported file types ──────────────────────────────────
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".csv", ".md"}


class DocumentParserService:
    """
    Global utility for document text extraction and AI-driven categorization.

    Pipeline:
        1. Extract raw text from file (PDF/DOCX/TXT/CSV)
        2. Compute file hash for dedup
        3. Call Gemini to classify category + extract entities
        4. Return unified JSON schema
    """

    def __init__(self):
        self._parse_log_path = os.path.join(FACTORY_DIR, "MASTER_INDEX.md")
        self._seen_hashes: set = set()

    # ═══════════════════════════════════════════════════════
    #  PUBLIC API
    # ═══════════════════════════════════════════════════════

    def parse(self, file_path: str, source_app: str = "unknown") -> dict:
        """
        Parse a document and return a unified JSON result.

        Args:
            file_path: Absolute path to the document
            source_app: Name of the app that owns this file

        Returns:
            dict with parse_id, category, entities, routing info
        """
        file_path = os.path.abspath(file_path)
        file_name = os.path.basename(file_path)
        ext = os.path.splitext(file_name)[1].lower()

        if ext not in SUPPORTED_EXTENSIONS:
            return {"error": f"Unsupported file type: {ext}", "supported": list(SUPPORTED_EXTENSIONS)}

        if not os.path.exists(file_path):
            return {"error": f"File not found: {file_path}"}

        parse_id = str(uuid.uuid4())
        logger.info(f"[{parse_id[:8]}] Parsing: {file_name} (source: {source_app})")

        # Step 1: Compute hash for dedup
        file_hash = self._compute_hash(file_path)
        if file_hash in self._seen_hashes:
            logger.info(f"[{parse_id[:8]}] Skipped — already parsed (hash: {file_hash[:16]})")
            return {"parse_id": parse_id, "status": "skipped", "reason": "duplicate", "file_hash": file_hash}
        self._seen_hashes.add(file_hash)

        # Step 2: Extract raw text
        raw_text = self._extract_text(file_path, ext)
        if not raw_text or raw_text.startswith("ERROR:"):
            return {"parse_id": parse_id, "status": "error", "error": raw_text or "No text extracted"}

        # Step 3: AI categorization + entity extraction
        ai_result = self._ai_analyze(raw_text, file_name)

        # Step 4: Build unified result
        result = {
            "parse_id": parse_id,
            "timestamp": datetime.now().isoformat(),
            "source_app": source_app,
            "file_name": file_name,
            "file_hash": f"sha256:{file_hash}",
            "category": ai_result.get("category", "Other"),
            "confidence": ai_result.get("confidence", 0.0),
            "extracted": {
                "summary": ai_result.get("summary", ""),
                "entities": ai_result.get("entities", {}),
                "raw_text_preview": raw_text[:500],
            },
            "routing": {
                "destination": None,
                "endpoint": None,
                "status": "pending",
            },
            "status": "parsed",
        }

        logger.info(f"[{parse_id[:8]}] Category: {result['category']} "
                     f"(confidence: {result['confidence']:.0%})")

        return result

    def is_supported(self, file_path: str) -> bool:
        """Check if a file type is supported for parsing."""
        ext = os.path.splitext(file_path)[1].lower()
        return ext in SUPPORTED_EXTENSIONS

    def was_already_parsed(self, file_path: str) -> bool:
        """Check if a file was already parsed (by hash)."""
        if not os.path.exists(file_path):
            return False
        file_hash = self._compute_hash(file_path)
        return file_hash in self._seen_hashes

    def log_to_master_index(self, result: dict):
        """Append a parse entry to MASTER_INDEX.md."""
        if result.get("status") != "parsed":
            return

        entry = f"""
### PARSE_ENTRY
- **Timestamp:** {result['timestamp']}
- **Source_App:** {result['source_app']}
- **File:** {result['file_name']}
- **Category:** {result['category']}
- **Confidence:** {result['confidence']:.0%}
- **Entities:** {self._summarize_entities(result['extracted'].get('entities', {}))}
- **Routed_To:** {result['routing'].get('destination', 'N/A')}
- **Status:** {result['routing'].get('status', 'pending').upper()}
"""
        try:
            with open(self._parse_log_path, "a", encoding="utf-8") as f:
                f.write(entry)
            logger.info(f"[{result['parse_id'][:8]}] Logged to MASTER_INDEX.md")
        except Exception as e:
            logger.error(f"Failed to log: {e}")

    # ═══════════════════════════════════════════════════════
    #  TEXT EXTRACTION
    # ═══════════════════════════════════════════════════════

    def _extract_text(self, file_path: str, ext: str) -> str:
        """Extract raw text from a file based on its extension."""
        try:
            if ext == ".pdf":
                return self._extract_pdf(file_path)
            elif ext in (".docx", ".doc"):
                return self._extract_docx(file_path)
            elif ext == ".csv":
                return self._extract_csv(file_path)
            elif ext in (".txt", ".md"):
                return self._extract_plaintext(file_path)
            else:
                return f"ERROR: Unsupported extension {ext}"
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return f"ERROR: {e}"

    def _extract_pdf(self, path: str) -> str:
        try:
            import pdfplumber
            text_parts = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text_parts.append(t)
            return "\n\n".join(text_parts) if text_parts else "ERROR: No text found in PDF"
        except ImportError:
            # Fallback: try PyPDF2
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(path)
                text_parts = [page.extract_text() or "" for page in reader.pages]
                return "\n\n".join(text_parts) if any(text_parts) else "ERROR: No text in PDF"
            except ImportError:
                return "ERROR: Install pdfplumber or PyPDF2 for PDF support (pip install pdfplumber)"

    def _extract_docx(self, path: str) -> str:
        try:
            from docx import Document
            doc = Document(path)
            return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except ImportError:
            return "ERROR: Install python-docx for DOCX support (pip install python-docx)"

    def _extract_csv(self, path: str) -> str:
        import csv
        rows = []
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            for i, row in enumerate(reader):
                if i > 100:  # Cap at 100 rows for preview
                    rows.append(f"... ({i} total rows)")
                    break
                rows.append(" | ".join(row))
        return "\n".join(rows)

    def _extract_plaintext(self, path: str) -> str:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    # ═══════════════════════════════════════════════════════
    #  AI CATEGORIZATION (Gemini)
    # ═══════════════════════════════════════════════════════

    def _ai_analyze(self, text: str, file_name: str) -> dict:
        """Use Gemini to categorize and extract entities from document text."""
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            logger.warning("GEMINI_API_KEY not set — falling back to keyword categorization")
            return self._keyword_categorize(text)

        prompt = f"""Analyze this document and return a JSON object with:
1. "category": One of {CATEGORIES}
2. "confidence": 0.0-1.0 how confident you are
3. "summary": 2-3 sentence executive summary
4. "entities": object with arrays for "dates", "amounts", "parties", "action_items"

Document filename: {file_name}
Document text (first 3000 chars):
{text[:3000]}

Respond ONLY with valid JSON, no markdown fences."""

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024},
            }
            _v3_status = safe_post(url, payload)

            r = type("Resp", (), {"status_code": 200 if _v3_status == "sent" else 503, "ok": _v3_status == "sent", "text": _v3_status, "json": lambda: {"status": _v3_status}})()
            if r.status_code != 200:
                logger.warning(f"Gemini API error: {r.status_code}")
                return self._keyword_categorize(text)

            response_text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            # Strip markdown fences if present
            response_text = response_text.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("\n", 1)[1].rsplit("```", 1)[0]

            return json.loads(response_text)

        except Exception as e:
            logger.warning(f"AI analysis failed ({e}) — using keyword fallback")
            return self._keyword_categorize(text)

    def _keyword_categorize(self, text: str) -> dict:
        """Fallback categorization using keyword matching."""
        text_lower = text.lower()

        scores = {
            "Legal": sum(1 for k in ["contract", "agreement", "clause", "liability", "indemnify",
                                      "jurisdiction", "hereby", "whereas", "attorney", "court"]
                        if k in text_lower),
            "Finance": sum(1 for k in ["invoice", "payment", "balance", "revenue", "profit",
                                        "tax", "budget", "quarterly", "fiscal", "accounting"]
                          if k in text_lower),
            "Ops": sum(1 for k in ["schedule", "deadline", "milestone", "task", "project",
                                    "timeline", "deliverable", "action item", "resource", "workflow"]
                      if k in text_lower),
            "Medical": sum(1 for k in ["patient", "diagnosis", "treatment", "clinical", "therapy",
                                        "medication", "symptom", "prognosis", "iep", "assessment"]
                          if k in text_lower),
            "Technical": sum(1 for k in ["api", "database", "deploy", "server", "architecture",
                                          "microservice", "endpoint", "docker", "kubernetes", "ci/cd"]
                            if k in text_lower),
        }

        best = max(scores, key=scores.get)
        best_score = scores[best]
        total = sum(scores.values()) or 1

        if best_score == 0:
            return {"category": "Other", "confidence": 0.5, "summary": "Could not categorize", "entities": {}}

        return {
            "category": best,
            "confidence": round(min(best_score / max(total, 1), 1.0), 2),
            "summary": f"Document classified as {best} based on keyword analysis.",
            "entities": {"dates": [], "amounts": [], "parties": [], "action_items": []},
        }

    # ═══════════════════════════════════════════════════════
    #  ACTIVITY EXTRACTION (Sentinel Bridge integration)
    # ═══════════════════════════════════════════════════════

    def extract_activities(self, raw_text: str, file_name: str = "") -> list[dict]:
        """
        Extract individual activities/tasks from document text.

        Each activity is returned as:
            {
                "activity": "short action title",
                "description": "detailed description",
                "due_date": "ISO date or null",
                "category": "one of CATEGORIES",
                "priority": "high|normal|low"
            }

        Uses Gemini for intelligent extraction, falls back to
        regex-based extraction if unavailable.
        """
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            logger.warning("GEMINI_API_KEY not set — using fallback activity extraction")
            return self._fallback_extract_activities(raw_text)

        prompt = f"""You are analyzing a document to extract EVERY individual task, activity, 
obligation, deadline, action item, or scheduled event mentioned.

For EACH activity found, return a JSON object with:
- "activity": short title (max 80 chars)
- "description": 1-2 sentence detailed description of what needs to happen
- "due_date": ISO date string (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS) if any date/deadline is mentioned, otherwise null
- "category": one of {CATEGORIES} — classify what business domain this activity belongs to
- "priority": "high" if it's urgent/legal/financial, "normal" otherwise, "low" if informational

Return a JSON array of these objects. If no activities are found, return an empty array [].

Document filename: {file_name}
Current date for reference: {datetime.now().strftime('%Y-%m-%d')}

Document text (first 4000 chars):
{raw_text[:4000]}

Respond ONLY with a valid JSON array, no markdown fences."""

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096},
            }
            _v3_status = safe_post(url, payload)

            r = type("Resp", (), {"status_code": 200 if _v3_status == "sent" else 503, "ok": _v3_status == "sent", "text": _v3_status, "json": lambda: {"status": _v3_status}})()
            if r.status_code != 200:
                logger.warning(f"Gemini API error: {r.status_code}")
                return self._fallback_extract_activities(raw_text)

            response_text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            response_text = response_text.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("\n", 1)[1].rsplit("```", 1)[0]

            activities = json.loads(response_text)
            if not isinstance(activities, list):
                activities = [activities]

            # Validate and sanitize each activity
            validated = []
            for act in activities:
                validated.append({
                    "activity": str(act.get("activity", "Untitled"))[:120],
                    "description": str(act.get("description", ""))[:300],
                    "due_date": act.get("due_date"),
                    "category": act.get("category", "Other") if act.get("category") in CATEGORIES else "Other",
                    "priority": act.get("priority", "normal") if act.get("priority") in ("high", "normal", "low") else "normal",
                })

            logger.info(f"Extracted {len(validated)} activities from {file_name}")
            return validated

        except Exception as e:
            logger.warning(f"AI activity extraction failed ({e}) — using fallback")
            return self._fallback_extract_activities(raw_text)

    def _fallback_extract_activities(self, text: str) -> list[dict]:
        """Regex-based fallback for activity extraction when Gemini is unavailable."""
        import re
        activities = []

        # Look for bullet points, numbered lists, action items
        patterns = [
            r'(?:^|\n)\s*[\-\*•]\s+(.+)',           # bullet points
            r'(?:^|\n)\s*\d+[\.\)]\s+(.+)',           # numbered lists
            r'(?:action item|TODO|TASK|deadline)[:\s]+(.+)',  # explicit markers
            r'(?:must|shall|will|should)\s+(.{10,80})',       # obligation verbs
        ]

        seen = set()
        for pat in patterns:
            for match in re.finditer(pat, text, re.IGNORECASE):
                item = match.group(1).strip()[:120]
                if item and item.lower() not in seen and len(item) > 5:
                    seen.add(item.lower())

                    # Try to extract a date nearby
                    date_match = re.search(
                        r'(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})',
                        text[max(0, match.start()-50):match.end()+100]
                    )
                    due = None
                    if date_match:
                        try:
                            raw_date = date_match.group(1)
                            if '/' in raw_date:
                                parts = raw_date.split('/')
                                if len(parts[2]) == 2:
                                    parts[2] = '20' + parts[2]
                                due = f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
                            else:
                                due = raw_date
                        except Exception:
                            pass

                    cat = self._keyword_categorize(item).get("category", "Other")
                    activities.append({
                        "activity": item,
                        "description": item,
                        "due_date": due,
                        "category": cat,
                        "priority": "normal",
                    })

        return activities[:20]  # Cap at 20 activities

    # ═══════════════════════════════════════════════════════
    #  UTILITIES
    # ═══════════════════════════════════════════════════════

    def _compute_hash(self, file_path: str) -> str:
        """Compute SHA-256 hash of a file for dedup."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _summarize_entities(self, entities: dict) -> str:
        """Create a short summary of extracted entities."""
        parts = []
        for key, values in entities.items():
            if values:
                parts.append(f"{len(values)} {key}")
        return ", ".join(parts) if parts else "None"


# ═══════════════════════════════════════════════════════════
#  STANDALONE TEST
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    parser = argparse.ArgumentParser(description="DocumentParserService — Test Mode")
    parser.add_argument("file", help="Path to document to parse")
    parser.add_argument("--app", default="test", help="Source app name")
    args = parser.parse_args()

    svc = DocumentParserService()
    result = svc.parse(args.file, source_app=args.app)

    print(json.dumps(result, indent=2, default=str))

    if result.get("status") == "parsed":
        svc.log_to_master_index(result)
        print("\n✅ Logged to MASTER_INDEX.md")
# V3 AUTO-HEAL ACTIVE

# V3 MIGRATION COMPLETE
