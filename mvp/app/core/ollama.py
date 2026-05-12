"""
Thin async wrappers per Ollama — embedding e generazione.
Usati sia da ingest.py che da query.py.
"""

import httpx

from app.core.config import settings


async def embed(text: str) -> list[float]:
    """Genera l'embedding di un testo via nomic-embed-text."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/embeddings",
            json={"model": settings.embed_model, "prompt": text},
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]


async def generate(prompt: str, num_predict: int = 1024, num_ctx: int = 4096) -> str:
    """Genera testo con il chat model."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/generate",
            json={
                "model": settings.chat_model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": num_predict, "num_ctx": num_ctx},
            },
            timeout=180.0,
        )
        resp.raise_for_status()
        return resp.json()["response"]


async def health_check() -> bool:
    """Verifica che Ollama sia raggiungibile."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.ollama_base_url}/api/tags", timeout=5.0
            )
            return resp.status_code == 200
    except Exception:
        return False
