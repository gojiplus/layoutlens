"""Using LayoutLens as an eval-harness judge: judge() and judge_batch().

Unlike analyze(), judge() sends YOUR prompt verbatim — no persona, no
scaffolding, no appended JSON contract — and never caches, so the harness
owns determinism. judge_batch() sends the byte-identical payload through
provider batch APIs (~50% cheaper) with a resumable manifest.
"""

import asyncio

from layoutlens import BatchRequest, LayoutLens, batch_usage_summary

PROMPT = """You are judging a rendered web page.
Question: Is the primary call-to-action visually prominent?
Respond with JSON: {"answer": "yes"|"no", "confidence": 0-1, "rationale": "..."}
"""


async def single_judgment():
    """One verbatim-prompt judgment with a parsed, auditable result."""
    lens = LayoutLens(model="gpt-4o-mini")

    result = await lens.judge("screenshot.png", PROMPT)

    print(f"answer:       {result.answer}")
    print(f"confidence:   {result.confidence}")
    print(f"rationale:    {result.rationale}")
    print(f"parse_mode:   {result.parse_mode}")  # json | fallback | none
    print(f"refused:      {result.refused}")
    print(f"truncated:    {result.truncated}")
    print(f"model:        {result.model}")
    print(f"prompt_sha256: {result.prompt_sha256[:16]}...")  # contract pinning
    print(f"tokens:       {result.usage}")


async def batch_judgments():
    """Thousands of judgments through the provider batch API, resumably."""
    lens = LayoutLens(model="gpt-4o-mini")

    requests = [
        BatchRequest(id=f"case-{i}", image_path=f"shots/case_{i}.png", prompt=PROMPT)
        for i in range(100)
    ]

    # A manifest persists submitted job ids BEFORE polling: a killed run
    # resumes and never re-bills recovered work.
    results = await lens.judge_batch(requests)

    summary = batch_usage_summary(results)
    print(f"requests:  {summary['requests']}")
    print(f"refused:   {summary['refused']}")
    print(f"unparsed:  {summary['unparsed']}")
    print(f"tokens:    {summary['total_tokens']}")
    print(f"est. cost: ${summary['estimated_cost_usd']}")


if __name__ == "__main__":
    asyncio.run(single_judgment())
