"""
Antigravity Self-Rectification Engine — "Reason in Chains, Learn in Trees"
==========================================================================
Nerve Center v2.0 | Core Intelligence Module

Implements tree-based error classification with grafting-based learning.
When the static REMEDY_LIBRARY cannot classify an error, this engine:

1. Decomposes the error into distinctive tokens
2. Traverses a reasoning tree to find the closest ancestor
3. Proposes a candidate diagnosis with auto-generated patterns
4. Grafts a provisional low-confidence branch onto the tree
5. After remedy outcome, promotes (boosts) or demotes (reduces) confidence

Architecture:
    ReasoningNode            — Single node in the diagnostic tree
    ReasoningTree            — Traversable, persistent tree structure
    LearningPipeline         — Outcome tracking + branch promotion/demotion
    SelfRectificationEngine  — Orchestrator

Persistence:
    ~/.antigravity/nerve_center_v2/reasoning_tree.json
    ~/.antigravity/nerve_center_v2/learning_ledger.json
"""

import os
import sys
import json
import re
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field


# ══════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════

STATE_DIR = os.path.join(os.path.expanduser("~"), ".antigravity", "nerve_center_v2")
TREE_FILE = os.path.join(STATE_DIR, "reasoning_tree.json")
LEDGER_FILE = os.path.join(STATE_DIR, "learning_ledger.json")

# Stop words filtered from token extraction (too generic for diagnosis)
STOP_WORDS = frozenset({
    "the", "a", "an", "is", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "need",
    "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "about", "up", "out", "after", "before",
    "and", "or", "but", "not", "no", "if", "then", "than",
    "this", "that", "these", "those", "it", "its",
    "error", "message", "occurred", "failed", "failure",
})


# ══════════════════════════════════════════════════════════════
#  SEED REMEDY LIBRARY (inherited from Nerve Center v1.0)
# ══════════════════════════════════════════════════════════════

SEED_REMEDIES = [
    {
        "id": "AUTH_EXPIRED",
        "name": "Expired/Invalid Authentication",
        "patterns": [r"401", r"Unauthorized", r"invalid.*token", r"auth.*fail"],
        "severity": "high",
        "action": "refresh_credentials",
        "description": "API token expired or invalid. Attempt credential refresh from vault/env.",
        "max_retries": 1,
    },
    {
        "id": "MALFORMED_JSON",
        "name": "Malformed JSON Body",
        "patterns": [r"400", r"Bad Request", r"JSON.*parse", r"Unexpected token", r"invalid.*json"],
        "severity": "medium",
        "action": "retry_execution",
        "description": "Request body contained malformed JSON. Retry with sanitized payload.",
        "max_retries": 2,
    },
    {
        "id": "GATEWAY_TIMEOUT",
        "name": "Upstream Gateway Timeout",
        "patterns": [r"504", r"Gateway Timeout", r"upstream.*timeout", r"ETIMEDOUT"],
        "severity": "medium",
        "action": "retry_with_backoff",
        "description": "Upstream service timed out. Retry with exponential backoff.",
        "max_retries": 3,
    },
    {
        "id": "RATE_LIMITED",
        "name": "Rate Limit Exceeded",
        "patterns": [r"429", r"Too Many Requests", r"rate.*limit", r"quota.*exceeded"],
        "severity": "medium",
        "action": "retry_with_backoff",
        "description": "API rate limit hit. Apply exponential backoff before retry.",
        "max_retries": 3,
    },
    {
        "id": "CONNECTION_REFUSED",
        "name": "Service Unreachable",
        "patterns": [r"ECONNREFUSED", r"Connection refused", r"ENOTFOUND", r"connect.*fail"],
        "severity": "high",
        "action": "retry_with_backoff",
        "description": "Target service is down or unreachable. Wait and retry.",
        "max_retries": 3,
    },
    {
        "id": "CIRCUIT_OPEN",
        "name": "Circuit Breaker Tripped",
        "patterns": [r"Circuit.*OPEN", r"circuit.*breaker", r"cascade.*fail"],
        "severity": "critical",
        "action": "reset_circuit_breaker",
        "description": "Circuit breaker is in OPEN state. Reset after verification.",
        "max_retries": 1,
    },
    {
        "id": "INTERNAL_ERROR",
        "name": "Internal Server Error",
        "patterns": [r"500", r"Internal Server Error", r"internal.*error"],
        "severity": "critical",
        "action": "log_for_review",
        "description": "Internal server error. Logged for manual review — no blind retry.",
        "max_retries": 0,
    },
    {
        "id": "WEBHOOK_DELIVERY",
        "name": "Webhook Delivery Failure",
        "patterns": [r"webhook.*fail", r"delivery.*fail", r"trigger.*error"],
        "severity": "medium",
        "action": "retry_execution",
        "description": "Webhook trigger failed. Retry the execution.",
        "max_retries": 2,
    },
    {
        "id": "NODE_CONFIG_ERROR",
        "name": "Node Configuration Error",
        "patterns": [r"node.*config", r"missing.*parameter", r"required.*field", r"undefined.*variable"],
        "severity": "high",
        "action": "log_for_review",
        "description": "Node misconfiguration detected. Requires manual intervention.",
        "max_retries": 0,
    },
]


# ══════════════════════════════════════════════════════════════
#  REASONING NODE — Atomic unit of the diagnostic tree
# ══════════════════════════════════════════════════════════════

@dataclass
class ReasoningNode:
    """A single node in the diagnostic reasoning tree."""
    id: str
    hypothesis: str                                     # Human-readable diagnosis name
    patterns: List[str]                                 # Regex patterns that indicate this diagnosis
    confidence: float = 1.0                             # 0.0 → 1.0 (promotion/demotion adjustable)
    remedy_id: Optional[str] = None                     # Points to the remedy this node prescribes
    remedy: Optional[Dict[str, Any]] = None             # {action, severity, max_retries, description}
    children: List['ReasoningNode'] = field(default_factory=list)
    match_count: int = 0                                # Total times this node was selected
    success_count: int = 0                              # Times the remedy succeeded
    learned: bool = False                               # True if grafted by the learning pipeline
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # ── Serialization ──
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "hypothesis": self.hypothesis,
            "patterns": self.patterns,
            "confidence": self.confidence,
            "remedy_id": self.remedy_id,
            "remedy": self.remedy,
            "children": [c.to_dict() for c in self.children],
            "match_count": self.match_count,
            "success_count": self.success_count,
            "learned": self.learned,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ReasoningNode':
        children = [cls.from_dict(c) for c in data.get("children", [])]
        return cls(
            id=data["id"],
            hypothesis=data["hypothesis"],
            patterns=data.get("patterns", []),
            confidence=data.get("confidence", 1.0),
            remedy_id=data.get("remedy_id"),
            remedy=data.get("remedy"),
            children=children,
            match_count=data.get("match_count", 0),
            success_count=data.get("success_count", 0),
            learned=data.get("learned", False),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )

    @property
    def success_rate(self) -> float:
        """Percentage of successful healing actions from this node."""
        if self.match_count == 0:
            return 0.0
        return round(self.success_count / self.match_count, 3)


# ══════════════════════════════════════════════════════════════
#  REASONING TREE — Traversable, persistent diagnostic tree
# ══════════════════════════════════════════════════════════════

class ReasoningTree:
    """
    Tree-structured error classification system.

    - Traverses from root to leaf to find the best diagnostic match
    - Supports grafting new branches when novel errors are learned
    - Persists to JSON on disk
    """

    def __init__(self, tree_path: str = TREE_FILE):
        self.tree_path = tree_path
        self.root = self._load_or_seed()

    # ── Initialization ──────────────────────────────────────
    def _load_or_seed(self) -> ReasoningNode:
        """Load existing tree from disk, or seed a fresh one from REMEDY_LIBRARY."""
        if os.path.exists(self.tree_path):
            try:
                with open(self.tree_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return ReasoningNode.from_dict(data)
            except Exception:
                pass
        return self._seed_tree()

    def _seed_tree(self) -> ReasoningNode:
        """Build the initial reasoning tree from the v1.0 SEED_REMEDIES."""
        root = ReasoningNode(
            id="ROOT",
            hypothesis="Error Classification Root",
            patterns=[],
            confidence=1.0,
        )
        for remedy in SEED_REMEDIES:
            child = ReasoningNode(
                id=remedy["id"],
                hypothesis=remedy["name"],
                patterns=remedy["patterns"],
                confidence=0.95,
                remedy_id=remedy["id"],
                remedy={
                    "action": remedy["action"],
                    "severity": remedy["severity"],
                    "max_retries": remedy["max_retries"],
                    "description": remedy["description"],
                },
                learned=False,
            )
            root.children.append(child)
        return root

    # ── Persistence ─────────────────────────────────────────
    def save(self):
        """Persist the tree to disk."""
        os.makedirs(os.path.dirname(self.tree_path), exist_ok=True)
        with open(self.tree_path, "w", encoding="utf-8") as f:
            json.dump(self.root.to_dict(), f, indent=2, default=str)

    # ── Traversal ───────────────────────────────────────────
    def traverse(self, error_text: str) -> Tuple[Optional[ReasoningNode], float]:
        """
        Walk the tree to find the best matching diagnosis node.

        Returns (best_node, aggregate_score) or (None, 0.0) if no match.
        Deeper matches get a small bonus (more specific = better).
        """
        match_text = error_text.lower()
        best_node: Optional[ReasoningNode] = None
        best_score: float = 0.0

        def _score_node(node: ReasoningNode) -> float:
            if not node.patterns:
                return 0.0
            hits = 0
            for pattern in node.patterns:
                try:
                    if re.search(pattern, match_text, re.IGNORECASE):
                        hits += 1
                except re.error:
                    # Fallback to literal substring match if regex is invalid
                    if pattern.lower() in match_text:
                        hits += 1
            if hits == 0:
                return 0.0
            return (hits / len(node.patterns)) * node.confidence

        def _walk(node: ReasoningNode, depth: int = 0):
            nonlocal best_node, best_score
            score = _score_node(node)
            if score > 0:
                # Depth bonus: deeper (more specific) matches score slightly higher
                adjusted = score + (depth * 0.05)
                if adjusted > best_score:
                    best_score = adjusted
                    best_node = node
            for child in node.children:
                _walk(child, depth + 1)

        _walk(self.root)
        return best_node, best_score

    # ── Grafting ────────────────────────────────────────────
    def graft(self, parent_id: str, new_node: ReasoningNode) -> bool:
        """
        Graft a new branch onto the tree at the specified parent.

        If a node with the same ID already exists, its patterns are
        merged and confidence is boosted instead of creating a duplicate.
        Returns True on success.
        """
        # Check for ID collision — merge instead of duplicate
        existing = self.find_node(new_node.id)
        if existing:
            existing.patterns = list(set(existing.patterns + new_node.patterns))
            existing.confidence = min(1.0, existing.confidence + 0.1)
            return True

        parent = self.find_node(parent_id)
        if parent is None:
            parent = self.root

        parent.children.append(new_node)
        return True

    # ── Lookup ──────────────────────────────────────────────
    def find_node(self, node_id: str) -> Optional[ReasoningNode]:
        """Find a node by ID (depth-first search)."""
        return self._find_recursive(self.root, node_id)

    def _find_recursive(self, node: ReasoningNode, node_id: str) -> Optional[ReasoningNode]:
        if node.id == node_id:
            return node
        for child in node.children:
            found = self._find_recursive(child, node_id)
            if found:
                return found
        return None

    # ── Statistics ──────────────────────────────────────────
    def get_stats(self) -> Dict[str, Any]:
        """Return tree statistics."""
        total = 0
        learned = 0
        max_depth = 0

        def _count(node: ReasoningNode, depth: int = 0):
            nonlocal total, learned, max_depth
            total += 1
            if node.learned:
                learned += 1
            max_depth = max(max_depth, depth)
            for child in node.children:
                _count(child, depth + 1)

        _count(self.root)
        return {
            "total_nodes": total,
            "learned_nodes": learned,
            "seeded_nodes": total - learned - 1,  # Subtract root
            "max_depth": max_depth,
        }


# ══════════════════════════════════════════════════════════════
#  LEARNING PIPELINE — Outcome tracking + promotion/demotion
# ══════════════════════════════════════════════════════════════

class LearningPipeline:
    """
    Tracks remedy outcomes and manages the learning ledger.

    - Successful novel remedies → PROMOTED (confidence boost + permanent graft)
    - Failed novel remedies → DEMOTED (confidence drop, flagged if too low)
    """

    def __init__(self, ledger_path: str = LEDGER_FILE):
        self.ledger_path = ledger_path
        self.pending: Dict[str, dict] = {}   # execution_id → pending attempt
        self.ledger = self._load_ledger()

    def _load_ledger(self) -> List[dict]:
        if os.path.exists(self.ledger_path):
            try:
                with open(self.ledger_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def save_ledger(self):
        os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)
        with open(self.ledger_path, "w", encoding="utf-8") as f:
            json.dump(self.ledger, f, indent=2, default=str)

    def register_attempt(
        self,
        execution_id: str,
        node_id: str,
        remedy_action: str,
        error_text: str,
        is_learned: bool,
    ):
        """Register a pending remedy attempt for outcome tracking."""
        self.pending[execution_id] = {
            "execution_id": execution_id,
            "node_id": node_id,
            "remedy_action": remedy_action,
            "error_text": error_text[:500],
            "is_learned": is_learned,
            "timestamp": datetime.now().isoformat(),
        }

    def record_outcome(
        self,
        execution_id: str,
        success: bool,
        tree: ReasoningTree,
    ) -> Optional[dict]:
        """
        Record the outcome of a remedy attempt.

        Successful learned remedies → boost confidence (PROMOTED)
        Failed learned remedies → reduce confidence (DEMOTED)

        Returns the ledger entry, or None if execution_id not found.
        """
        attempt = self.pending.pop(execution_id, None)
        if not attempt:
            return None

        entry = {
            **attempt,
            "success": success,
            "resolved_at": datetime.now().isoformat(),
            "action": "OBSERVED",  # Default; overridden below for learned nodes
        }

        # Update the tree node's statistics
        node = tree.find_node(attempt["node_id"])
        if node:
            node.match_count += 1
            if success:
                node.success_count += 1
                if attempt["is_learned"]:
                    node.confidence = min(1.0, node.confidence + 0.15)
                    entry["action"] = "PROMOTED"
            else:
                if attempt["is_learned"]:
                    node.confidence = max(0.1, node.confidence - 0.2)
                    entry["action"] = "DEMOTED"
                    if node.confidence < 0.3:
                        entry["flag"] = "LOW_CONFIDENCE_REVIEW"

        self.ledger.append(entry)
        self.ledger = self.ledger[-500:]  # Cap at 500 entries
        self.save_ledger()
        tree.save()
        return entry


# ══════════════════════════════════════════════════════════════
#  SELF-RECTIFICATION ENGINE — Orchestrator
# ══════════════════════════════════════════════════════════════

class SelfRectificationEngine:
    """
    Orchestrates tree-based error classification with learning.

    For known errors  → traverses the reasoning tree directly
    For unknown errors → enters RECTIFICATION mode:
        1. Decompose error into distinctive tokens
        2. Find closest ancestor in the tree
        3. Generate candidate regex patterns
        4. Propose a remedy (inferred from error characteristics)
        5. Graft a provisional low-confidence branch
        6. Track outcome for promotion/demotion
    """

    # Minimum score for a tree traversal match to be considered "confident"
    CONFIDENCE_THRESHOLD = 0.3

    def __init__(self, state_dir: str = STATE_DIR):
        self.state_dir = state_dir
        os.makedirs(state_dir, exist_ok=True)

        tree_path = os.path.join(state_dir, "reasoning_tree.json")
        ledger_path = os.path.join(state_dir, "learning_ledger.json")

        self.tree = ReasoningTree(tree_path)
        self.pipeline = LearningPipeline(ledger_path)

    # ── Primary API ─────────────────────────────────────────
    def diagnose(
        self,
        error_text: str,
        execution_id: str = "",
        workflow_name: str = "Unknown",
    ) -> Dict[str, Any]:
        """
        Diagnose an error using the reasoning tree.

        Returns a diagnosis dict compatible with the v1.0 NerveCenter API.
        If no confident match is found, enters rectification mode.
        """
        # Phase 1: Traverse the tree for a confident match
        node, score = self.tree.traverse(error_text)

        if node and score >= self.CONFIDENCE_THRESHOLD and node.remedy:
            # Confident match — return directly
            node.match_count += 1
            self.tree.save()

            # Register for outcome tracking (even seeded nodes)
            self.pipeline.register_attempt(
                execution_id=execution_id,
                node_id=node.id,
                remedy_action=node.remedy.get("action", "log_for_review"),
                error_text=error_text,
                is_learned=node.learned,
            )

            return {
                "id": node.remedy_id or node.id,
                "name": node.hypothesis,
                "severity": node.remedy.get("severity", "medium"),
                "action": node.remedy.get("action", "log_for_review"),
                "description": node.remedy.get("description", node.hypothesis),
                "max_retries": node.remedy.get("max_retries", 0),
                "confidence": round(score, 3),
                "source": "learned" if node.learned else "seeded",
                "error_message": error_text[:500],
                "workflow_name": workflow_name,
                "execution_id": execution_id,
                "matched_node": node.id,
            }

        # Phase 2: Rectification — unknown error type
        return self._rectify(error_text, execution_id, workflow_name, node)

    def learn(self, execution_id: str, success: bool) -> Optional[dict]:
        """Feed back the outcome of a remedy to the learning pipeline."""
        return self.pipeline.record_outcome(execution_id, success, self.tree)

    # ── Rectification (private) ─────────────────────────────
    def _rectify(
        self,
        error_text: str,
        execution_id: str,
        workflow_name: str,
        closest_node: Optional[ReasoningNode],
    ) -> Dict[str, Any]:
        """
        Rectification mode for unrecognized errors.

        1. Extract distinctive tokens from the error text
        2. Determine closest ancestor and inherit its action strategy
        3. Generate candidate regex patterns from tokens
        4. Create a provisional low-confidence node
        5. Graft it onto the tree and register for outcome tracking
        """
        # Step 1: Token extraction
        tokens = self._extract_tokens(error_text)

        # Step 2: Closest ancestor → action inheritance
        if closest_node and closest_node.remedy:
            parent_id = closest_node.id
            proposed_action = closest_node.remedy.get("action", "retry_with_backoff")
            proposed_severity = closest_node.remedy.get("severity", "medium")
            max_retries = closest_node.remedy.get("max_retries", 1)
        else:
            parent_id = "ROOT"
            proposed_action = self._infer_action(error_text, tokens)
            proposed_severity = self._infer_severity(error_text, tokens)
            max_retries = 1

        # Step 3: Candidate patterns
        candidate_patterns = self._generate_patterns(tokens, error_text)

        # Step 4: Node identity
        token_hash = hashlib.md5(
            "_".join(sorted(tokens[:5])).encode()
        ).hexdigest()[:8].upper()
        node_id = f"LEARNED_{token_hash}"

        # Step 5: Hypothesis
        hypothesis = f"Learned: {' + '.join(tokens[:3])}"
        if len(tokens) > 3:
            hypothesis += f" (+{len(tokens) - 3} more)"

        # Step 6: Create and graft the provisional node
        new_node = ReasoningNode(
            id=node_id,
            hypothesis=hypothesis,
            patterns=candidate_patterns,
            confidence=0.4,     # Low initial confidence
            remedy_id=node_id,
            remedy={
                "action": proposed_action,
                "severity": proposed_severity,
                "max_retries": max_retries,
                "description": f"Auto-learned remedy for: {hypothesis}",
            },
            learned=True,
        )

        self.tree.graft(parent_id, new_node)
        self.tree.save()

        # Register for outcome tracking
        self.pipeline.register_attempt(
            execution_id=execution_id,
            node_id=node_id,
            remedy_action=proposed_action,
            error_text=error_text,
            is_learned=True,
        )

        return {
            "id": node_id,
            "name": hypothesis,
            "severity": proposed_severity,
            "action": proposed_action,
            "description": f"Auto-learned remedy for: {hypothesis}",
            "max_retries": max_retries,
            "confidence": 0.4,
            "source": "rectified",
            "error_message": error_text[:500],
            "workflow_name": workflow_name,
            "execution_id": execution_id,
            "matched_node": node_id,
            "parent_node": parent_id,
            "candidate_patterns": candidate_patterns,
        }

    # ── Token Extraction ────────────────────────────────────
    def _extract_tokens(self, error_text: str) -> List[str]:
        """
        Extract distinctive tokens from error text for pattern generation.

        Filters stop words, deduplicates, and returns top 15 tokens
        ordered by appearance.
        """
        text = error_text.lower()
        raw_tokens = re.findall(r'[a-zA-Z_]+|\d{3,}', text)
        filtered = [
            t for t in raw_tokens
            if t.lower() not in STOP_WORDS and len(t) >= 3
        ]
        # Deduplicate preserving order
        seen = set()
        unique = []
        for t in filtered:
            tl = t.lower()
            if tl not in seen:
                seen.add(tl)
                unique.append(tl)
        return unique[:15]

    # ── Pattern Generation ──────────────────────────────────
    def _generate_patterns(self, tokens: List[str], error_text: str) -> List[str]:
        """
        Generate regex patterns from extracted tokens.

        - Single-token patterns (high recall)
        - Bigram proximity patterns (high precision)
        """
        patterns = []

        # Individual tokens (top 5)
        for token in tokens[:5]:
            patterns.append(re.escape(token))

        # Bigram proximity patterns (tokens within 50 chars of each other)
        text_lower = error_text.lower()
        for i in range(min(len(tokens) - 1, 3)):
            t1, t2 = tokens[i], tokens[i + 1]
            if t1 in text_lower and t2 in text_lower:
                idx1 = text_lower.find(t1)
                idx2 = text_lower.find(t2)
                if abs(idx2 - idx1) < 50:
                    patterns.append(f"{re.escape(t1)}.*{re.escape(t2)}")

        return patterns[:8]   # Cap at 8 patterns

    # ── Action Inference ────────────────────────────────────
    def _infer_action(self, error_text: str, tokens: List[str]) -> str:
        """Infer the best remedy action from error characteristics (no LLM)."""
        text = error_text.lower()

        # Timeout / connectivity → retry with backoff
        if any(kw in text for kw in [
            "timeout", "timed out", "connection", "refused",
            "unreachable", "econnrefused", "enotfound",
        ]):
            return "retry_with_backoff"

        # Rate limiting → backoff
        if any(kw in text for kw in ["rate", "limit", "throttl", "quota"]):
            return "retry_with_backoff"

        # Authentication → refresh
        if any(kw in text for kw in [
            "auth", "token", "credential", "permission",
            "forbidden", "401", "403",
        ]):
            return "refresh_credentials"

        # Data/format → simple retry
        if any(kw in text for kw in [
            "parse", "format", "invalid", "malformed",
            "unexpected", "syntax",
        ]):
            return "retry_execution"

        # Default: conservative retry with backoff
        return "retry_with_backoff"

    def _infer_severity(self, error_text: str, tokens: List[str]) -> str:
        """Infer severity from error characteristics (no LLM)."""
        text = error_text.lower()

        if any(kw in text for kw in [
            "fatal", "crash", "corrupt", "data loss",
            "circuit", "cascade", "panic",
        ]):
            return "critical"

        if any(kw in text for kw in [
            "auth", "permission", "denied", "refused",
            "security", "forbidden",
        ]):
            return "high"

        return "medium"

    # ── Status ──────────────────────────────────────────────
    def get_stats(self) -> Dict[str, Any]:
        """Return engine statistics for dashboards."""
        tree_stats = self.tree.get_stats()
        return {
            "engine": "Nerve Center v2.0 — Self-Rectification",
            "tree": tree_stats,
            "learning_ledger_size": len(self.pipeline.ledger),
            "pending_outcomes": len(self.pipeline.pending),
        }
