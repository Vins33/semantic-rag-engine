"""
Thin async HTTP client wrapping the RAG backend API.
"""
from __future__ import annotations

import os

import httpx

API_BASE = os.getenv("API_BASE", "http://localhost:8000")
_timeout = httpx.Timeout(300.0)  # LLM calls can take ~120s


class ApiClient:
    def __init__(self, token: str = ""):
        self.token = token

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    # ── auth ──────────────────────────────────────────────────────────────
    async def login(self, sub: str, role: str) -> str:
        async with httpx.AsyncClient(timeout=_timeout) as c:
            r = await c.post(f"{API_BASE}/api/v1/auth/token",
                             json={"sub": sub, "role": role})
            r.raise_for_status()
            self.token = r.json()["access_token"]
            return self.token

    # ── health ────────────────────────────────────────────────────────────
    async def health(self) -> dict:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{API_BASE}/api/v1/health")
            return r.json()

    # ── metrics ───────────────────────────────────────────────────────────
    async def metrics_raw(self) -> str:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{API_BASE}/metrics/")
            return r.text

    # ── query ─────────────────────────────────────────────────────────────
    async def query(self, question: str, top_k: int = 6) -> dict:
        async with httpx.AsyncClient(timeout=_timeout) as c:
            r = await c.post(f"{API_BASE}/api/v1/query",
                             json={"query": question, "top_k": top_k},
                             headers=self._headers())
            r.raise_for_status()
            return r.json()

    # ── ingest ────────────────────────────────────────────────────────────
    async def ingest(self, filename: str, content: bytes) -> dict:
        async with httpx.AsyncClient(timeout=_timeout) as c:
            r = await c.post(f"{API_BASE}/api/v1/ingest",
                             files={"file": (filename, content)},
                             headers={"Authorization": f"Bearer {self.token}"})
            r.raise_for_status()
            return r.json()

    # ── eval ──────────────────────────────────────────────────────────────
    async def evaluate(self, query: str, answer: str, context: str) -> dict:
        async with httpx.AsyncClient(timeout=_timeout) as c:
            r = await c.post(f"{API_BASE}/api/v1/eval",
                             json={"query": query, "answer": answer, "context": context},
                             headers=self._headers())
            r.raise_for_status()
            return r.json()

    # ── tuner ─────────────────────────────────────────────────────────────
    async def tuner_params(self) -> dict:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{API_BASE}/api/v1/tuner/params",
                            headers=self._headers())
            r.raise_for_status()
            return r.json()

    # ── entities ──────────────────────────────────────────────────────────
    async def search_entities(self, q: str) -> list:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{API_BASE}/api/v1/entities/search",
                            params={"query": q},
                            headers=self._headers())
            r.raise_for_status()
            return r.json()

    async def kg_context(self, entity: str) -> dict:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{API_BASE}/api/v1/kg/context/{entity}",
                            headers=self._headers())
            r.raise_for_status()
            return r.json()

    # ── chats ─────────────────────────────────────────────────────────────
    async def chat_create(self, title: str = "Nuova chat") -> dict:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{API_BASE}/api/v1/chats",
                             json={"title": title},
                             headers=self._headers())
            r.raise_for_status()
            return r.json()

    async def chat_list(self) -> list:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{API_BASE}/api/v1/chats", headers=self._headers())
            r.raise_for_status()
            return r.json()

    async def chat_rename(self, chat_id: str, title: str) -> None:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.patch(f"{API_BASE}/api/v1/chats/{chat_id}",
                              json={"title": title},
                              headers=self._headers())
            r.raise_for_status()

    async def chat_delete(self, chat_id: str) -> None:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.delete(f"{API_BASE}/api/v1/chats/{chat_id}",
                               headers=self._headers())
            r.raise_for_status()

    async def chat_messages(self, chat_id: str) -> list:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{API_BASE}/api/v1/chats/{chat_id}/messages",
                            headers=self._headers())
            r.raise_for_status()
            return r.json()

    async def chat_append(self, chat_id: str, role: str, content: str, meta: dict | None = None) -> None:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{API_BASE}/api/v1/chats/{chat_id}/messages",
                             json={"role": role, "content": content, "meta": meta or {}},
                             headers=self._headers())
            r.raise_for_status()

