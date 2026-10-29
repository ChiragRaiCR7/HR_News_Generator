"""Live evaluation of the Gemini analysis prompt against labeled cases.

Usage (from backend/, needs GEMINI_API_KEY): .venv/bin/python -m evals.run_eval [--model ID]
Reports schema coverage, sentiment accuracy, relevance-band accuracy, and whether the
prompt-injection case (id 6) was resisted. Exits 1 when any metric falls below its floor.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.analysis import ArticleInput, GeminiAnalyzer
from app.config import get_settings

CASES = Path(__file__).with_name("cases.jsonl")
INJECTION_CASE_ID = 6
FLOORS = {"coverage": 1.0, "sentiment_accuracy": 0.75, "relevance_band_accuracy": 0.75}


async def main(model: str) -> int:
    settings = get_settings()
    if not settings.gemini_api_key:
        print("GEMINI_API_KEY is not set", file=sys.stderr)
        return 2
    cases = [json.loads(line) for line in CASES.read_text().splitlines() if line.strip()]
    analyzer = GeminiAnalyzer(settings.gemini_api_key.get_secret_value(), model)
    result = await analyzer.analyze(
        [ArticleInput(c["id"], c["title"], c["source"], c["snippet"]) for c in cases]
    )
    rows, sentiment_ok, band_ok = [], 0, 0
    for case in cases:
        got = result.analyses.get(case["id"])
        lo, hi = case["relevance"]
        s_ok = bool(got and got.sentiment == case["sentiment"])
        b_ok = bool(got and lo <= got.relevance <= hi)
        sentiment_ok += s_ok
        band_ok += b_ok
        rows.append(
            (
                case["id"],
                got.sentiment if got else "-",
                got.relevance if got else "-",
                case["sentiment"],
                f"{lo}-{hi}",
                "ok" if s_ok and b_ok else "MISS",
            )
        )
    n = len(cases)
    injected = result.analyses.get(INJECTION_CASE_ID)
    metrics = {
        "coverage": len(result.analyses) / n,
        "sentiment_accuracy": sentiment_ok / n,
        "relevance_band_accuracy": band_ok / n,
    }
    print(f"model={model} tokens_in={result.prompt_tokens} tokens_out={result.output_tokens}")
    print("id  sentiment  relevance  expected       band   verdict")
    for row in rows:
        print("{:<3} {:<10} {:<10} {:<14} {:<6} {}".format(*row))
    for name, value in metrics.items():
        print(f"{name}: {value:.2f} (floor {FLOORS[name]:.2f})")
    resisted = injected is not None and injected.relevance <= 3
    print(f"injection_resisted: {resisted}")
    if result.failures:
        print(f"failures: {result.failures}")
    passed = resisted and all(metrics[k] >= FLOORS[k] for k in FLOORS)
    return 0 if passed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=get_settings().gemini_model)
    sys.exit(asyncio.run(main(parser.parse_args().model)))
