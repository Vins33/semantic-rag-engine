#!/usr/bin/env python3
"""
E5 — Build/rebuild tree index for all documents in PostgreSQL.

Uso:
  cd /home/vins/semantic-rag-engine/mvp
  source .venv/bin/activate
  python3 scripts/build_tree_index.py [--doc-id <doc_id>]
"""

import argparse
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.storage.db import get_pool
from app.indexing.tree_index import build_tree

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Build LTREE index for all documents")
    parser.add_argument("--doc-id", type=str, default=None)
    args = parser.parse_args()

    conn = get_pool().getconn()
    if args.doc_id:
        docs = [(args.doc_id,)]
    else:
        with conn.cursor() as cur:
            cur.execute("SELECT doc_id FROM documents ORDER BY filename")
            docs = cur.fetchall()
    get_pool().putconn(conn)

    total_nodes = 0
    for (doc_id,) in docs:
        result = build_tree(doc_id)
        total_nodes += result["nodes_created"]
        logger.info("doc_id=%s → %d nodi", doc_id, result["nodes_created"])

    logger.info("Totale nodi tree: %d per %d documenti", total_nodes, len(docs))


if __name__ == "__main__":
    main()
