# Kalibr

> Execution path routing for AI agents. Not a model router.

## What It Does

Kalibr routes AI agent requests across execution paths — complete configurations of model + tool + parameters — based on system telemetry and learned outcomes. When a path degrades, Kalibr detects it and routes around it automatically.

## Quick Start

from kalibr import Router

router = Router(
    goal="extract_company",
    paths=["gpt-4o", "claude-sonnet-4-20250514", "gemini-2.0-flash"],
)

response = router.completion(
    messages=[{"role": "user", "content": "Extract the company: Hi from Stripe."}]
)
router.report(success=True)

## Links

- Docs: https://kalibr.systems/docs
- Dashboard: https://dashboard.kalibr.systems
- PyPI: https://pypi.org/project/kalibr/
- LangChain package: https://pypi.org/project/langchain-kalibr/
