"""
Prompts per la governance e la valutazione automatica.

  EVAL_FAITHFULNESS   → verifica che la risposta sia supportata dal contesto
  EVAL_RELEVANCY      → verifica che la risposta sia rilevante alla domanda
  EVAL_RECALL         → verifica che il contesto copra il ground_truth
"""

EVAL_FAITHFULNESS = """\
You are an expert evaluator. Given the CONTEXT and the ANSWER, assess whether all claims in the ANSWER are supported by the CONTEXT.

CONTEXT:
{context}

ANSWER:
{answer}

Instructions:
- Score 1.0 if every claim in the answer is explicitly or implicitly supported by the context.
- Score 0.0 if the answer contains claims not found in the context.
- Use intermediate values for partial support.
- Respond ONLY with a JSON object: {{"score": <float 0.0-1.0>, "reason": "<brief explanation>"}}
"""

EVAL_RELEVANCY = """\
You are an expert evaluator. Given the QUESTION and the ANSWER, assess how relevant the answer is to the question.

QUESTION:
{query}

ANSWER:
{answer}

Instructions:
- Score 1.0 if the answer directly and completely addresses the question.
- Score 0.0 if the answer is completely off-topic.
- Respond ONLY with a JSON object: {{"score": <float 0.0-1.0>, "reason": "<brief explanation>"}}
"""

EVAL_RECALL = """\
You are an expert evaluator. Given the GROUND TRUTH and the CONTEXT retrieved, assess how well the context covers the information in the ground truth.

GROUND TRUTH:
{ground_truth}

CONTEXT:
{context}

Instructions:
- Score 1.0 if the context contains all the information present in the ground truth.
- Score 0.0 if the context is missing all key information.
- Respond ONLY with a JSON object: {{"score": <float 0.0-1.0>, "reason": "<brief explanation>"}}
"""
