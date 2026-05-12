"""
EvalService — incapsula la valutazione RAGAS via LLM.

Uso:
  service = EvalService()
  result = await service.evaluate(query, answer, context, ground_truth)
"""

import json
import logging
import re
from typing import Optional

from app.core import ollama
from app.models.governance import EvalMetric, EvalResult
from app.prompts.governance import EVAL_FAITHFULNESS, EVAL_RELEVANCY, EVAL_RECALL

logger = logging.getLogger(__name__)


class EvalService:
    """RAGAS-style evaluation using a local LLM (gemma4)."""

    # ── Score parser ─────────────────────────────────────────────────────────

    @staticmethod
    def _parse_score(text: str) -> EvalMetric:
        match = re.search(r'\{[^{}]*"score"\s*:\s*[\d.]+[^{}]*\}', text, re.DOTALL)
        if match:
            try:
                obj = json.loads(match.group())
                score = max(0.0, min(1.0, float(obj.get("score", 0.5))))
                return EvalMetric(score=score, reason=obj.get("reason", ""))
            except (json.JSONDecodeError, ValueError):
                pass
        num = re.search(r'"score"\s*:\s*([\d.]+)', text)
        if num:
            try:
                score = max(0.0, min(1.0, float(num.group(1))))
                return EvalMetric(score=score, reason=text[:200])
            except ValueError:
                pass
        logger.warning("EvalService: cannot parse score from: %s", text[:200])
        return EvalMetric(score=0.5, reason="parse error")

    # ── Main entrypoint ──────────────────────────────────────────────────────

    async def evaluate(
        self,
        query: str,
        answer: str,
        context: str,
        ground_truth: Optional[str] = None,
    ) -> EvalResult:
        # Faithfulness
        faith_raw = await ollama.generate(
            EVAL_FAITHFULNESS.format(context=context[:3000], answer=answer[:1500]),
            num_predict=512, num_ctx=4096,
        )
        faithfulness = self._parse_score(faith_raw)

        # Answer relevancy
        relev_raw = await ollama.generate(
            EVAL_RELEVANCY.format(query=query, answer=answer[:1500]),
            num_predict=512, num_ctx=2048,
        )
        relevancy = self._parse_score(relev_raw)

        # Context recall (optional)
        recall: Optional[EvalMetric] = None
        if ground_truth:
            recall_raw = await ollama.generate(
                EVAL_RECALL.format(ground_truth=ground_truth[:1500], context=context[:3000]),
                num_predict=512, num_ctx=4096,
            )
            recall = self._parse_score(recall_raw)

        scores = [faithfulness.score, relevancy.score]
        if recall:
            scores.append(recall.score)
        overall = round(sum(scores) / len(scores), 3)

        return EvalResult(
            faithfulness=faithfulness,
            answer_relevancy=relevancy,
            context_recall=recall,
            overall=overall,
        )
