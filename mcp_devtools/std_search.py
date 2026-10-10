"""Search over the v8std standards corpus (pages.jsonl).

The corpus lives in the v8std checkout: docs/ai/pages.jsonl — one JSON per
line with id, title, aliases and body_markdown for each standard. This
module gives exact/alias/full-text retrieval so the agent can cite a
standard by ID instead of guessing.

No external dependencies. Read-only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

Word_RE = re.compile(r"[a-zа-яё0-9#]+", re.IGNORECASE)


class StdCorpus:
    def __init__(self, jsonl_path: str):
        self.path = Path(jsonl_path)
        self.pages: List[Dict[str, Any]] = []
        self.by_id: Dict[str, Dict[str, Any]] = {}
        self.by_std_num: Dict[str, Dict[str, Any]] = {}
        self._loaded = False

    def load(self) -> "StdCorpus":
        if self._loaded:
            return self
        if not self.path.exists():
            raise FileNotFoundError(f"v8std corpus not found: {self.path}")
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # accept both {id:...} and {"page": {...}} envelopes
                page = rec.get("page") if isinstance(rec.get("page"), dict) else rec
                pid = str(page.get("id") or page.get("ID") or "")
                if not pid:
                    continue
                self.pages.append(page)
                self.by_id[pid.lower()] = page
                m = re.search(r"#?std[_ ]?(\d+)", pid, re.IGNORECASE)
                if m:
                    self.by_std_num[m.group(1)] = page
        self._loaded = True
        return self

    # ---------- retrieval ----------

    def get(self, std_id: str) -> Optional[Dict[str, Any]]:
        """Exact standard by id (#std396 / std396 / 396)."""
        s = std_id.strip().lower().lstrip("#")
        if s in self.by_id:
            return self.by_id[s]
        m = re.search(r"std[_ ]?(\d+)", s)
        if m and m.group(1) in self.by_std_num:
            return self.by_std_num[m.group(1)]
        if s.isdigit() and s in self.by_std_num:
            return self.by_std_num[s]
        return None

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Alias and full-text search, alias hits ranked first."""
        q = query.strip().lower()
        if not q:
            return []
        scored: List[tuple] = []
        qwords = set(Word_RE.findall(q))
        for page in self.pages:
            aliases = [str(a).lower() for a in (page.get("aliases") or [])]
            title = str(page.get("title") or page.get("name") or "")
            score = 0
            # exact alias
            if q in aliases:
                score = 100
            # alias substring
            elif any(q in a for a in aliases):
                score = 80
            # title substring
            elif q in title.lower():
                score = 60
            else:
                # full text word overlap
                body = str(page.get("body_markdown") or "")
                bwords = set(Word_RE.findall((title + " " + body).lower()))
                overlap = len(qwords & bwords)
                if overlap:
                    score = min(50, overlap * 2)
            if score:
                scored.append((score, page))
        scored.sort(key=lambda x: -x[0])
        return [
            {
                "id": p.get("id") or p.get("ID"),
                "title": p.get("title") or p.get("name") or "",
                "score": s,
                "aliases": (p.get("aliases") or [])[:5],
            }
            for s, p in scored[:limit]
        ]

    def body(self, std_id: str, char_limit: int = 4000) -> Optional[Dict[str, Any]]:
        page = self.get(std_id)
        if not page:
            return None
        body = str(page.get("body_markdown") or "")
        return {
            "id": page.get("id") or page.get("ID"),
            "title": page.get("title") or page.get("name") or "",
            "aliases": page.get("aliases") or [],
            "body": body[:char_limit],
            "truncated": len(body) > char_limit,
        }

    def stats(self) -> Dict[str, Any]:
        return {"pages": len(self.pages), "path": str(self.path)}
