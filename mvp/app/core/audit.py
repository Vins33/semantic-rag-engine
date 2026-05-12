"""
E6 — Merkle Audit Log.

Ogni evento (ingestione, query, cancellazione) viene registrato in audit_log
con hash concatenato a catena:

  entry_hash = SHA-256(prev_hash | event_type | doc_id | payload_json | ts_iso)

Garanzie:
  - Tamper-evidence: modificare qualsiasi entry invalida tutti gli hash successivi
  - Append-only: nessuna riga viene mai aggiornata/cancellata
  - Thread-safe: LOCK TABLE EXCLUSIVE durante read-compute-write

Tipi di evento:
  ingest   — documento indicizzato
  query    — query eseguita (doc_ids usati come evidenza)
  delete   — documento rimosso
  migrate  — arricchimento metadata su documento esistente
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from app.storage.db import get_pool

logger = logging.getLogger(__name__)

_GENESIS_HASH = "0" * 64


def _compute_hash(
    prev_hash: str,
    event_type: str,
    doc_id: str,
    payload: dict,
    ts: str,
) -> str:
    raw = f"{prev_hash}|{event_type}|{doc_id}|{json.dumps(payload, sort_keys=True)}|{ts}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _get_last_hash(cur) -> str:
    cur.execute(
        "SELECT entry_hash FROM audit_log ORDER BY entry_id DESC LIMIT 1"
    )
    row = cur.fetchone()
    return row[0] if row else _GENESIS_HASH


def log_event(
    event_type: str,
    doc_id: Optional[str],
    payload: dict,
) -> None:
    """
    Appende un evento al Merkle audit log.
    Fallisce silenziosamente se la tabella non esiste o il DB è irraggiungibile.
    """
    try:
        conn = get_pool().getconn()
        try:
            with conn.cursor() as cur:
                # Lock esclusivo per garantire l'atomicità della catena
                cur.execute("LOCK TABLE audit_log IN EXCLUSIVE MODE")
                prev_hash = _get_last_hash(cur)
                ts = datetime.now(timezone.utc).isoformat()
                entry_hash = _compute_hash(
                    prev_hash, event_type, doc_id or "", payload, ts
                )
                cur.execute(
                    """
                    INSERT INTO audit_log
                        (prev_hash, event_type, doc_id, payload, entry_hash, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        prev_hash,
                        event_type,
                        doc_id,
                        json.dumps(payload),
                        entry_hash,
                        ts,
                    ),
                )
            conn.commit()
        finally:
            get_pool().putconn(conn)
    except Exception as exc:
        logger.warning("Audit log write failed (non-fatal): %s", exc)


def verify_chain(limit: int = 100) -> dict:
    """
    Verifica l'integrità della catena Merkle sulle ultime `limit` entry.
    Ritorna {"valid": bool, "checked": int, "first_broken_id": int | None}.
    """
    try:
        conn = get_pool().getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT entry_id, prev_hash, event_type, doc_id, payload, entry_hash, created_at
                    FROM audit_log
                    ORDER BY entry_id DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
        finally:
            get_pool().putconn(conn)
    except Exception as exc:
        return {"valid": False, "checked": 0, "error": str(exc)}

    if not rows:
        return {"valid": True, "checked": 0, "first_broken_id": None}

    # Verifica ordine cronologico inverso
    rows = list(reversed(rows))
    broken_id = None

    for i, row in enumerate(rows):
        entry_id, prev_hash, event_type, doc_id, payload_raw, stored_hash, ts = row
        try:
            payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
        except Exception:
            payload = {}

        expected_prev = rows[i - 1][5] if i > 0 else _GENESIS_HASH
        if prev_hash != expected_prev:
            broken_id = entry_id
            break

        computed = _compute_hash(
            prev_hash,
            event_type,
            doc_id or "",
            payload,
            ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
        )
        if computed != stored_hash:
            broken_id = entry_id
            break

    return {
        "valid":           broken_id is None,
        "checked":         len(rows),
        "first_broken_id": broken_id,
    }
