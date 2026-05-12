"""
F3 — HyDE (Hypothetical Document Embeddings).

Tecnica: invece di embeddare direttamente la query dell'utente, si genera
un breve documento ipotetico che *risponde* alla query, poi si embeddano
entrambi e si usa la media per il retrieval.

Vantaggio: riduce il gap semantico query–documento, migliorando recall
soprattutto su query brevi o in linguaggio colloquiale.

Riferimento: Gao et al. "Precise Zero-Shot Dense Retrieval without Relevance Labels"
             arXiv:2212.10496
"""

import asyncio

from app.core import ollama

from app.prompts.rag import HYDE as _HYDE_PROMPT


async def hyde_embedding(query: str) -> list[float]:
    """
    Genera l'embedding HyDE per una query.

    1. Genera un documento ipotetico via LLM (llama3.2, ~100 token)
    2. Embeddà sia la query originale che il documento ipotetico
    3. Ritorna la media dei due vettori (query + HyDE)
    """
    prompt = _HYDE_PROMPT.format(query=query)

    # Genera documento ipotetico (512 token: reasoning models usano ~150 token interni)
    hypo_doc = await ollama.generate(prompt, num_predict=512)
    hypo_doc = hypo_doc.strip()

    # If LLM returned empty string, fall back to plain query embedding
    if not hypo_doc:
        return await ollama.embed(query)

    # Embedding parallelo: query originale + documento ipotetico
    query_vec, hypo_vec = await asyncio.gather(
        ollama.embed(query),
        ollama.embed(hypo_doc),
    )

    # Se uno dei due vettori è vuoto (Ollama timeout / empty), usa solo l'altro
    if not query_vec:
        return hypo_vec
    if not hypo_vec:
        return query_vec

    # Media dei due vettori (centro geometrico)
    avg = [(a + b) / 2.0 for a, b in zip(query_vec, hypo_vec)]
    return avg
