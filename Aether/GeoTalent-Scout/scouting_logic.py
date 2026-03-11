"""
scouting_logic.py — GeoTalent Scout Agent Core
=================================================
Project Aether | Meta_App_Factory | GeoTalent-Scout

Agentic talent scouting engine:
  1. Extract keywords from job descriptions
  2. Search for candidates (SerpApi-ready stub)
  3. Cross-reference against internal employee database
  4. Output structured candidate results

Usage:
    from scouting_logic import GeoTalentScout
    scout = GeoTalentScout()
    results = scout.scout("Production Line Worker", "Miami, FL", "Looking for...")
"""

import os
import re
import json
import logging
from datetime import datetime, timezone
from difflib import SequenceMatcher

logger = logging.getLogger("geotalent.scout")

# ── Paths ──────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FACTORY_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
ROOT_DIR = os.path.abspath(os.path.join(FACTORY_DIR, ".."))
EMPLOYEES_JSON = os.path.join(FACTORY_DIR, "data", "employees.json")
SYNC_LOG = os.path.join(ROOT_DIR, "SYNC_TEST_Mauro-Home-PC.txt")

# ── Certification & Skill Taxonomies ───────────────────────────
CERTIFICATION_PATTERNS = [
    r"\b(?:OSHA|HACCP|FDA|GMP|SQF|BRC|ISO\s?\d+|ServSafe|CPR|First\s?Aid)\b",
    r"\b(?:PMP|Six\s?Sigma|Lean|Kaizen|5S|CMMI|ITIL)\b",
    r"\b(?:CDL|CPA|CFA|PHR|SHRM|SPHR|ASE|EPA|HVAC)\b",
    r"\b(?:AWS|Azure|GCP|Kubernetes|Docker|CompTIA)\b",
    r"\b(?:Bilingual|Spanish|English|Portuguese|Creole)\b",
]

SKILL_KEYWORDS = {
    "production":    ["production", "manufacturing", "assembly", "line", "operator", "machine"],
    "quality":       ["quality", "QA", "QC", "inspection", "audit", "compliance", "testing"],
    "warehouse":     ["warehouse", "logistics", "shipping", "receiving", "forklift", "inventory"],
    "maintenance":   ["maintenance", "mechanic", "technician", "electrical", "plumbing", "HVAC"],
    "food_safety":   ["food safety", "sanitation", "HACCP", "SQF", "FDA", "GMP", "hygiene"],
    "management":    ["manager", "supervisor", "lead", "director", "coordinator", "team lead"],
    "admin":         ["administrative", "office", "clerical", "data entry", "reception", "HR"],
    "engineering":   ["engineer", "CAD", "design", "process", "automation", "PLC"],
    "sales":         ["sales", "account", "business development", "customer", "retail"],
    "accounting":    ["accounting", "bookkeeping", "payroll", "AP", "AR", "finance", "reporting"],
}


class GeoTalentScout:
    """
    Agentic talent scouting engine for the Aether ecosystem.
    """

    def __init__(self):
        self.employees = self._load_employees()
        self._log(f"GeoTalent Scout initialized | {len(self.employees)} internal records loaded")

    # ══════════════════════════════════════════════════════════════
    #  PUBLIC API
    # ══════════════════════════════════════════════════════════════

    def scout(self, role_title: str, location: str, job_description: str) -> dict:
        """
        Full scouting pipeline:
        1. Extract keywords + certifications from the job description
        2. Search external candidates (stub — ready for SerpApi)
        3. Cross-reference internal employee database
        4. Return merged, ranked results
        """
        self._log(f"SCOUT START | Role: {role_title} | Location: {location}")

        # 1. Keyword extraction
        extraction = self.extract_keywords(job_description)
        self._log(f"  Keywords: {extraction['keywords'][:5]}")
        self._log(f"  Certs: {extraction['certifications']}")
        self._log(f"  Skill Clusters: {list(extraction['skill_clusters'].keys())}")

        # 2. External search (stub)
        external = self.search_candidates(extraction["keywords"], location, role_title)

        # 3. Internal cross-reference
        internal = self.cross_reference_internal(
            extraction["keywords"],
            extraction["skill_clusters"],
            role_title,
            location,
        )

        # 4. Merge & rank
        all_candidates = internal + external
        all_candidates.sort(key=lambda c: c.get("match_score", 0), reverse=True)

        result = {
            "role_title": role_title,
            "location": location,
            "extraction": extraction,
            "candidates": all_candidates,
            "summary": {
                "total_found": len(all_candidates),
                "internal_matches": len(internal),
                "external_leads": len(external),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._log(f"SCOUT COMPLETE | {len(internal)} internal + {len(external)} external = {len(all_candidates)} total")
        return result

    def extract_keywords(self, job_description: str) -> dict:
        """
        Extract search parameters from a job description.
        Returns keywords, certifications, and skill cluster matches.
        """
        text = job_description.strip()
        text_lower = text.lower()

        # Extract certifications
        certs = set()
        for pattern in CERTIFICATION_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                certs.add(match.group(0).strip())

        # Extract skill cluster matches
        clusters = {}
        for cluster_name, terms in SKILL_KEYWORDS.items():
            matched = [t for t in terms if t.lower() in text_lower]
            if matched:
                clusters[cluster_name] = matched

        # General keyword extraction (nouns / meaningful words)
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "shall", "can", "to", "of", "in", "for",
            "on", "with", "at", "by", "from", "as", "into", "through", "during",
            "before", "after", "above", "below", "between", "and", "but", "or",
            "not", "no", "this", "that", "these", "those", "it", "its", "we",
            "our", "you", "your", "they", "their", "them", "he", "she", "his",
            "her", "who", "which", "what", "when", "where", "how", "all", "each",
            "every", "both", "few", "more", "most", "other", "some", "such",
            "than", "too", "very", "just", "also", "about", "up", "out", "if",
            "then", "so", "must", "need", "able", "per",
        }
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text_lower)
        keywords = list(dict.fromkeys(
            w for w in words if w not in stop_words
        ))[:20]  # Top 20 unique keywords

        return {
            "keywords": keywords,
            "certifications": sorted(certs),
            "skill_clusters": clusters,
            "raw_word_count": len(words),
        }

    def search_candidates(self, keywords: list, location: str, role_title: str) -> list:
        """
        Multi-source external candidate search using Aether Deep Crawler pattern:
        Step 1: Tavily/SerpApi/WebScrape → gather raw results
        Step 2: Gemini AI → classify CANDIDATE vs JOB_AD, extract real data
        Returns only verified candidate profiles.
        """
        raw_results = []

        # Source 1: Tavily deep search (AI-native search engine)
        tavily_key = os.getenv("TAVILY_API_KEY", "")
        if tavily_key:
            self._log("  [Tavily] Deep Crawler: Scanning for candidate profiles...")
            tavily_results = self._tavily_search(keywords, location, role_title, tavily_key)
            raw_results.extend(tavily_results)
            self._log(f"  [Tavily] Raw results: {len(tavily_results)}")
        else:
            self._log("  [Tavily] No API key — set TAVILY_API_KEY in .env")

        # Source 2: SerpApi Google search (if available)
        serp_key = os.getenv("SERP_API_KEY", "")
        if serp_key:
            self._log("  [SerpApi] Running Google search...")
            serp_results = self._serp_search(keywords, location, role_title, serp_key)
            raw_results.extend(serp_results)
            self._log(f"  [SerpApi] Raw results: {len(serp_results)}")

        # Source 3: Direct web scrape (no API key needed — fallback)
        if not raw_results:
            self._log("  [WebScrape] Running direct web scrape (fallback)...")
            scrape_results = self._web_scrape_search(keywords, location, role_title)
            raw_results.extend(scrape_results)
            self._log(f"  [WebScrape] Raw results: {len(scrape_results)}")

        # ── Aether Deep Crawler Pattern: AI Classification ──
        # Use Gemini to filter out job ads and extract real candidate data
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        if gemini_key and raw_results:
            self._log(f"  [Gemini] Classifying {len(raw_results)} raw results (CANDIDATE vs JOB_AD)...")
            raw_results = self._classify_and_extract(raw_results, role_title, keywords, location, gemini_key)
            self._log(f"  [Gemini] Verified candidates after filtering: {len(raw_results)}")
        else:
            # No Gemini — apply basic ad detection heuristic
            raw_results = [r for r in raw_results if not self._looks_like_ad(r)]

        # Deduplicate by name
        seen = set()
        unique = []
        for r in raw_results:
            name_key = r.get("name", "").lower().strip()
            if name_key and name_key not in seen:
                seen.add(name_key)
                unique.append(r)

        return unique

    def _tavily_search(self, keywords: list, location: str,
                       role_title: str, api_key: str) -> list:
        """
        Tavily deep search — Aether Deep Crawler pattern.
        Queries target CANDIDATE PROFILES (LinkedIn /in/, resumes, portfolios)
        rather than job listings.
        """
        try:
            import requests

            # ── Candidate-focused queries (NOT job ads) ──
            top_skills = ' '.join(keywords[:4])
            queries = [
                # LinkedIn profile pages (the /in/ path = personal profiles)
                f'site:linkedin.com/in/ "{role_title}" "{location}"',
                # Public resumes and CVs
                f'"{role_title}" resume "{location}" {top_skills} -hiring -"apply now" -"job opening"',
                # Professional directories and portfolios
                f'"{role_title}" "{location}" profile experience {top_skills} -jobs -careers -posting',
            ]

            all_results = []
            for query in queries:
                try:
                    resp = requests.post("https://api.tavily.com/search", json={
                        "api_key": api_key,
                        "query": query,
                        "search_depth": "advanced",
                        "include_answer": True,
                        "include_raw_content": True,  # Deep Crawler: get full page text
                        "max_results": 10,
                    }, timeout=30)

                    if resp.status_code != 200:
                        self._log(f"  [Tavily] Query failed ({resp.status_code}): {query[:60]}")
                        continue

                    data = resp.json()

                    for item in data.get("results", []):
                        title = item.get("title", "")
                        url = item.get("url", "")
                        content = item.get("content", "")
                        raw_content = item.get("raw_content", "")
                        score = item.get("score", 0.5)

                        # Determine platform from URL
                        platform = self._detect_platform(url)

                        # Use the richest content available
                        best_content = (raw_content or content or title)[:500]

                        # Extract name from the title
                        name = self._extract_name_from_title(title, role_title)

                        all_results.append({
                            "source": "External",
                            "name": name,
                            "match_score": round(min(score, 0.95), 2),
                            "location": location,
                            "platform": platform,
                            "contact": url,
                            "notes": content[:200] if content else title,
                            "raw_content": best_content,
                            "search_engine": "Tavily",
                        })

                except Exception as e:
                    self._log(f"  [Tavily] Query error: {e}")
                    continue

            return all_results

        except ImportError:
            self._log("  [Tavily] requests library not installed")
            return []
        except Exception as e:
            self._log(f"  [Tavily] Error: {e}")
            return []

    def _web_scrape_search(self, keywords: list, location: str,
                           role_title: str) -> list:
        """
        Direct web scrape fallback — no API key needed.
        Searches Google for candidate profiles (not job ads).
        """
        try:
            import requests
            from html.parser import HTMLParser

            class GoogleParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.results = []
                    self._in_result = False
                    self._current = {}
                    self._capture = False
                    self._text = ""

                def handle_starttag(self, tag, attrs):
                    attrs_dict = dict(attrs)
                    if tag == "a" and "href" in attrs_dict:
                        href = attrs_dict["href"]
                        if href.startswith("/url?q="):
                            url = href.split("/url?q=")[1].split("&")[0]
                            if "google.com" not in url:
                                self._current = {"url": url}
                                self._capture = True
                                self._text = ""
                    if tag in ("h3", "span") and self._capture:
                        self._capture = True

                def handle_data(self, data):
                    if self._capture:
                        self._text += data

                def handle_endtag(self, tag):
                    if tag == "a" and self._current:
                        if self._text.strip():
                            self._current["title"] = self._text.strip()
                            self.results.append(self._current)
                        self._current = {}
                        self._capture = False
                        self._text = ""

            # Profile-focused query: target LinkedIn profiles and resumes, exclude job ads
            top_skills = ' '.join(keywords[:3])
            query = f'site:linkedin.com/in/ "{role_title}" "{location}" {top_skills}'
            url = f"https://www.google.com/search?q={requests.utils.quote(query)}&num=15"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0"
            }

            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                self._log(f"  [WebScrape] Google returned {resp.status_code}")
                return []

            parser = GoogleParser()
            parser.feed(resp.text)

            results = []
            for item in parser.results[:10]:
                item_url = item.get("url", "")
                title = item.get("title", "Unknown")

                platform = self._detect_platform(item_url)
                name = self._extract_name_from_title(title, role_title)

                # Skip obvious ads even in scrape results
                if self._looks_like_ad({"name": name, "notes": title, "contact": item_url}):
                    continue

                results.append({
                    "source": "External",
                    "name": name,
                    "match_score": 0.40,
                    "location": location,
                    "platform": platform,
                    "contact": item_url,
                    "notes": title,
                    "search_engine": "Google Scrape",
                })

            return results

        except Exception as e:
            self._log(f"  [WebScrape] Error: {e}")
            return []

    # ── Gemini model fallback chain (Aether Runtime self-healing) ──
    _GEMINI_MODELS = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash-001",
    ]

    def _classify_and_extract(self, raw_results: list, role_title: str,
                              keywords: list, location: str, api_key: str) -> list:
        """
        Aether Deep Crawler + Atomizer self-healing pattern:
        1. Retry with model fallback chain (gemini-2.5-flash → 2.0-flash → lite)
        2. JSON array extraction from wrapped text (Atomizer pattern)
        3. Critic mini-gate: validate each classified candidate
        4. Graceful degradation to heuristic filter on total failure
        """
        import requests as _req
        import time

        # Build the batch of results for Gemini to classify
        items_for_ai = []
        batch_len = min(len(raw_results), 20)
        for i in range(batch_len):
            r = raw_results[i]
            items_for_ai.append(
                f"[{i}] Title: {r.get('name', 'N/A')} | "
                f"Platform: {r.get('platform', 'Web')} | "
                f"URL: {r.get('contact', '')} | "
                f"Content: {r.get('raw_content', r.get('notes', ''))[:300]}"
            )

        batch_text = "\n".join(items_for_ai)

        # Build prompt with string concat to avoid f-string brace escaping issues
        prompt = (
            'You are an expert HR talent scout AI. I searched the web for '
            f'candidates matching the role "{role_title}" in "{location}".\n'
            f'Required skills: {", ".join(keywords[:10])}\n\n'
            'Below are raw search results. For EACH result, classify it.\n\n'
            f'Raw Results:\n{batch_text}\n\n'
            'For EACH result, determine:\n'
            '1. "type": "CANDIDATE" (actual person profile/resume), '
            '"JOB_AD" (job listing/posting), or "IRRELEVANT"\n'
            '2. If CANDIDATE: extract "name" (real name), "title" (job title), '
            '"experience" (brief summary), "score" (0.0-1.0 relevance), '
            '"email" (if found in content, else null), '
            '"phone" (if found in content, else null)\n'
            '3. If JOB_AD or IRRELEVANT: just classify, no extraction needed\n\n'
            'Return ONLY a JSON array. Example:\n'
            '[{"index": 0, "type": "CANDIDATE", "name": "John Smith", '
            '"title": "Production Supervisor", '
            '"experience": "10 years food manufacturing", "score": 0.85, '
            '"email": "john@example.com", "phone": null}, '
            '{"index": 1, "type": "JOB_AD"}]\n\n'
            'JSON array only. No explanation.'
        )

        # ── Atomizer-style retry loop with model fallback ──
        for model_name in self._GEMINI_MODELS:
            try:
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/"
                    f"models/{model_name}:generateContent?key={api_key}"
                )
                self._log(f"  [Gemini] Trying model: {model_name}")

                gen_config = {
                    "temperature": 0.1,
                    "maxOutputTokens": 4096,
                }
                # Non-thinking models support responseMimeType for forced JSON
                if "2.5" not in model_name:
                    gen_config["responseMimeType"] = "application/json"

                resp = _req.post(url, json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": gen_config,
                }, timeout=45)

                if resp.status_code != 200:
                    self._log(f"  [Gemini] {model_name} returned {resp.status_code} — trying next model")
                    time.sleep(1)
                    continue

                # ── Handle thinking models (gemini-2.5-flash) ──
                # Thinking models return multiple parts:
                #   parts[0] = {thought: true, text: "reasoning..."}
                #   parts[1] = {text: "actual JSON answer"}
                # Non-thinking models return a single part.
                try:
                    candidate = resp.json()["candidates"][0]
                    parts = candidate.get("content", {}).get("parts", [])

                    # Search ALL parts for JSON array (skip thinking parts)
                    raw_text = ""
                    for part in parts:
                        if part.get("thought"):
                            continue  # Skip thinking block
                        text_content = part.get("text", "")
                        if "[" in text_content:
                            raw_text = text_content
                            break
                    # Fallback: concatenate all non-thinking parts
                    if not raw_text:
                        raw_text = " ".join(
                            p.get("text", "") for p in parts if not p.get("thought")
                        )
                except (KeyError, IndexError):
                    self._log(f"  [Gemini] {model_name} returned unexpected structure")
                    continue

                # ── Atomizer JSON extraction: find '[' ... ']' ──
                # Handles wrapped text, code fences, explanatory prefixes
                text = raw_text.strip()
                start = text.find('[')
                end = text.rfind(']')

                if start == -1 or end == -1 or end <= start:
                    self._log(f"  [Gemini] No JSON array found in response from {model_name}")
                    continue

                json_str = text[start:end + 1]

                try:
                    classifications = json.loads(json_str)
                except json.JSONDecodeError as je:
                    self._log(f"  [Gemini] JSON parse error on {model_name}: {je}")
                    continue  # Try next model

                # ── Critic mini-gate: validate each result ──
                verified = []
                ads_filtered = 0
                for item in classifications:
                    idx = item.get("index", -1)
                    result_type = item.get("type", "IRRELEVANT")

                    if result_type != "CANDIDATE" or idx < 0 or idx >= len(raw_results):
                        if result_type == "JOB_AD":
                            ads_filtered += 1
                        continue

                    original = raw_results[idx].copy()

                    # Critic check: reject if the "candidate" still looks like an ad
                    ai_name = item.get("name", original.get("name", ""))
                    if self._looks_like_ad({"name": ai_name, "notes": item.get("experience", ""), "contact": original.get("contact", "")}):
                        ads_filtered += 1
                        self._log(f"  [Critic Gate] Rejected: '{ai_name}' (ad pattern in AI-extracted data)")
                        continue

                    # Overwrite with AI-extracted data
                    if item.get("name"):
                        original["name"] = item["name"]
                    if item.get("title"):
                        original["extracted_title"] = item["title"]
                    if item.get("experience"):
                        original["notes"] = item["experience"]
                    if item.get("score"):
                        try:
                            original["match_score"] = round(min(float(item["score"]), 0.99), 2)
                        except (ValueError, TypeError):
                            pass
                    # Contact info extraction
                    platform = original.get("platform", "Web")
                    original["email"] = item.get("email") or ("N/A (LinkedIn)" if platform == "LinkedIn" else "")
                    original["phone"] = item.get("phone") or ("N/A (LinkedIn)" if platform == "LinkedIn" else "")
                    original["ai_verified"] = True
                    original["ai_model"] = model_name
                    # Remove raw_content from final output (too large for UI)
                    original.pop("raw_content", None)
                    verified.append(original)

                self._log(
                    f"  [Gemini] Classification SUCCESS ({model_name}): "
                    f"{len(verified)} candidates, {ads_filtered} ads filtered"
                )
                return verified

            except _req.exceptions.Timeout:
                self._log(f"  [Gemini] {model_name} timed out — trying next model")
                continue
            except Exception as e:
                self._log(f"  [Gemini] {model_name} error: {e} — trying next model")
                continue

        # ── All models exhausted — graceful degradation ──
        self._log("  [Self-Heal] All Gemini models failed. Applying heuristic filter.")
        filtered = [r for r in raw_results if not self._looks_like_ad(r)]
        # Strip raw_content from fallback results
        for r in filtered:
            r.pop("raw_content", None)
        return filtered

    # ── Ad Detection Heuristics ────────────────────────────────
    _AD_PATTERNS = re.compile(
        r'(?i)(apply now|job opening|hiring|now hiring|we are hiring|'
        r'jobs? near|careers? at|positions? available|'
        r'\$\d+[\./]hr|\$\d+[\./]hour|\$\d+k|salary|per hour|'
        r'job posting|post a job|get hired|looking to hire|'
        r'urgently hiring|immediately hiring|open position)',
    )

    _JOB_BOARD_DOMAINS = {
        "indeed.com", "ziprecruiter.com", "monster.com", "glassdoor.com",
        "careerbuilder.com", "simplyhired.com", "snagajob.com",
        "jobs.lever.co", "boards.greenhouse.io", "workday.com",
    }

    def _looks_like_ad(self, result: dict) -> bool:
        """Heuristic check: does this search result look like a job ad?"""
        combined = f"{result.get('name', '')} {result.get('notes', '')}".lower()
        url = result.get("contact", "").lower()

        # Check for job board domains (except LinkedIn profiles)
        if any(domain in url for domain in self._JOB_BOARD_DOMAINS):
            return True

        # Check ad language patterns
        if self._AD_PATTERNS.search(combined):
            return True

        return False

    @staticmethod
    def _detect_platform(url: str) -> str:
        """Detect the platform from a URL."""
        url_lower = url.lower()
        if "linkedin.com" in url_lower:
            return "LinkedIn"
        elif "indeed.com" in url_lower:
            return "Indeed"
        elif "glassdoor.com" in url_lower:
            return "Glassdoor"
        elif "ziprecruiter.com" in url_lower:
            return "ZipRecruiter"
        elif "monster.com" in url_lower:
            return "Monster"
        return "Web"

    def _extract_name_from_title(self, title: str, role_title: str) -> str:
        """Extract a candidate name from a search result title.
        Handles LinkedIn titles like 'John Smith - Production Manager - Company'
        and detects ad-like titles to return sanitized labels."""
        # Reject obvious ad titles
        if self._AD_PATTERNS.search(title):
            return f"[Ad Result] {title[:40]}"

        # Split by common separators and find the name part
        for sep in [" - ", " | ", " — ", " – "]:
            if sep in title:
                parts = title.split(sep)
                # LinkedIn: first part is the person's name
                candidate = parts[0].strip()
                # A real name is short and doesn't match the role title
                if (len(candidate) < 50
                    and candidate.lower() != role_title.lower()
                    and not self._AD_PATTERNS.search(candidate)):
                    return candidate

        # Truncate long titles
        return title[:60] if len(title) > 60 else title

    def cross_reference_internal(self, keywords: list, clusters: dict,
                                  role_title: str, location: str) -> list:
        """
        Cross-reference extracted keywords against the internal employee DB.
        Returns matching employees ranked by relevance score.
        """
        matches = []

        for emp in self.employees:
            score = 0.0
            match_reasons = []

            job_title = emp.get("Job Title", "").lower()
            full_name = emp.get("Full Name", "")
            zip_code = emp.get("ZIP/Postal Code", "")
            dept = emp.get("Department Code", "")
            status = emp.get("Status", emp.get("status", ""))

            # Title similarity
            title_sim = SequenceMatcher(None, role_title.lower(), job_title).ratio()
            if title_sim > 0.3:
                score += title_sim * 0.5
                match_reasons.append(f"title_match:{title_sim:.0%}")

            # Keyword overlap with job title
            for kw in keywords[:10]:
                if kw in job_title:
                    score += 0.15
                    match_reasons.append(f"keyword:{kw}")

            # Cluster match
            for cluster_name, terms in clusters.items():
                for term in terms:
                    if term.lower() in job_title:
                        score += 0.2
                        match_reasons.append(f"cluster:{cluster_name}")
                        break

            # Location proximity (ZIP code matching)
            if location and zip_code:
                loc_digits = re.findall(r"\d{5}", location)
                zip_digits = re.findall(r"\d{5}", zip_code)
                if loc_digits and zip_digits and loc_digits[0][:3] == zip_digits[0][:3]:
                    score += 0.15
                    match_reasons.append("zip_proximity")

            # Threshold filter
            if score >= 0.15:
                matches.append({
                    "source": "Internal",
                    "name": full_name,
                    "match_score": round(min(score, 1.0), 2),
                    "job_title": emp.get("Job Title", ""),
                    "department": dept,
                    "zip_code": zip_code,
                    "email": emp.get("Home Email", ""),
                    "phone": emp.get("Mobile Phone", ""),
                    "employee_number": emp.get("Employee Number", ""),
                    "status": status,
                    "match_reasons": match_reasons,
                })

        # Sort by score descending
        matches.sort(key=lambda m: m["match_score"], reverse=True)
        return matches[:25]  # Top 25

    def get_all_employees(self) -> list:
        """Return the full internal employee list."""
        return self.employees

    # ══════════════════════════════════════════════════════════════
    #  PRIVATE HELPERS
    # ══════════════════════════════════════════════════════════════

    def _load_employees(self) -> list:
        """Load employees from the parsed JSON file."""
        if not os.path.exists(EMPLOYEES_JSON):
            logger.warning("employees.json not found at %s", EMPLOYEES_JSON)
            return []
        try:
            with open(EMPLOYEES_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to load employees: %s", e)
            return []

    def _serp_search(self, keywords: list, location: str,
                     role_title: str, api_key: str) -> list:
        """
        Live SerpApi search. Activate by setting SERP_API_KEY.
        """
        try:
            import requests
            query = f"{role_title} {' '.join(keywords[:5])} {location}"
            resp = requests.get("https://serpapi.com/search", params={
                "api_key": api_key,
                "q": query,
                "engine": "google",
                "num": 10,
            }, timeout=15)
            data = resp.json()
            results = []
            for item in data.get("organic_results", [])[:10]:
                results.append({
                    "source": "External",
                    "name": item.get("title", "Unknown"),
                    "match_score": 0.5,
                    "location": location,
                    "platform": item.get("displayed_link", "Web"),
                    "contact": item.get("link", ""),
                    "notes": item.get("snippet", ""),
                })
            return results
        except Exception as e:
            logger.error("SerpApi search failed: %s", e)
            return []

    def _log(self, message: str):
        """Log to both logger and SYNC_TEST file for real-time debugging."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] GeoTalent | {message}"
        logger.info(message)
        try:
            with open(SYNC_LOG, "a", encoding="utf-8") as f:
                f.write(log_line + "\n")
        except Exception:
            pass  # Non-critical — sync log may not be writable


# ── CLI Test ───────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scout = GeoTalentScout()
    result = scout.scout(
        role_title="Production Line Worker",
        location="Miami, FL 33064",
        job_description=(
            "Seeking a Production Line Worker for our food manufacturing facility. "
            "Must have HACCP certification, experience with GMP standards, "
            "bilingual English/Spanish preferred. Forklift experience a plus. "
            "Responsible for machine operation, quality checks, and sanitation."
        ),
    )
    print(json.dumps(result, indent=2))
