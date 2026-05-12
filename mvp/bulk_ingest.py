#!/usr/bin/env python3
"""
Bulk ingest — indicizza tutti i PDF in una cartella (ricorsivamente).
Uso:
    python3 bulk_ingest.py [directory]   default: ../papers
"""

import asyncio
import sys
from pathlib import Path
import httpx

API_BASE = "http://localhost:8000"
API_URL  = f"{API_BASE}/api/v1/ingest"
AUTH_URL = f"{API_BASE}/api/v1/auth/token"
TIMEOUT  = 300  # secondi per PDF


async def get_token(client: httpx.AsyncClient) -> str:
    resp = await client.post(AUTH_URL, json={"sub": "bulk_ingest", "role": "writer"}, timeout=10)
    resp.raise_for_status()
    return resp.json()["access_token"]


async def ingest_one(client: httpx.AsyncClient, pdf: Path, idx: int, total: int, token: str) -> dict:
    try:
        with pdf.open("rb") as f:
            resp = await client.post(
                API_URL,
                files={"file": (pdf.name, f, "application/pdf")},
                headers={"Authorization": f"Bearer {token}"},
                timeout=TIMEOUT,
            )
        data = resp.json()
        if resp.status_code == 201:
            print(f"  [{idx}/{total}] ✓ {pdf.name}  ({data['chunks_created']} chunks)")
        elif "già presente" in data.get("detail", ""):
            print(f"  [{idx}/{total}] ↷ {pdf.name}  (già indicizzato)")
        else:
            print(f"  [{idx}/{total}] ✗ {pdf.name}  {data.get('detail','errore')}")
        return data
    except Exception as exc:
        print(f"  [{idx}/{total}] ✗ {pdf.name}  eccezione: {exc}")
        return {"error": str(exc)}


async def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../papers")
    pdfs = sorted(root.rglob("*.pdf"))
    if not pdfs:
        print(f"Nessun PDF trovato in {root}")
        return

    print(f"Trovati {len(pdfs)} PDF in '{root}'")
    print("Ingestione in corso (sequenziale per rispettare Ollama)...\n")

    async with httpx.AsyncClient() as client:
        token = await get_token(client)
        for i, pdf in enumerate(pdfs, 1):
            await ingest_one(client, pdf, i, len(pdfs), token)

    print("\nFatto.")


if __name__ == "__main__":
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
