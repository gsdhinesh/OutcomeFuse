"""Smoke-test the live model port against the deployment. Costs money.

    pip install openai azure-identity
    az login
    .venv/Scripts/python.exe scripts/smoke_model.py

Run with the venv's interpreter rather than `uv run`: the two libraries above
are not declared dependencies, so a sync would remove them.

One call per deployment, tiny prompt. It exists to answer the questions a fake
client cannot: does the credential work, does the endpoint accept what we send,
and what does the usage accounting actually look like on this deployment. That
last one matters most — the reasoning-token share is the number that decides
whether the OFF/ON signal survives, and guessing it would be guessing at the
feasibility of the whole benchmark.
"""

from __future__ import annotations

import sys

from outcomefuse.adapters.model import AzureFoundryModelPort, ModelPortError
from outcomefuse.ports import ModelRequest, user_turn

BASE_URL = "https://outcomefuse-foundry.services.ai.azure.com/openai/v1"

#: The frozen baseline definition's settings, so this exercises what will run.
REASONING_EFFORT = "medium"
MAX_OUTPUT_TOKENS = 25_000

PROMPT = "Reply with exactly the word: ready"


def main() -> int:
    try:
        port = AzureFoundryModelPort(base_url=BASE_URL)
    except ModelPortError as exc:
        # Missing libraries or no credential. A traceback here would bury the
        # one line that says what to do about it.
        print(f"cannot reach the deployment: {exc}")
        return 1
    failures = 0

    for model_id in ("gpt-5-mini", "gpt-5"):
        print(f"\n=== {model_id} ===")
        try:
            response = port.complete(
                ModelRequest(
                    model_id=model_id,
                    messages=user_turn(PROMPT),
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                    reasoning_effort=REASONING_EFFORT,
                )
            )
        except ModelPortError as exc:
            # One line, not the credential chain's whole autobiography.
            print(f"FAILED  {str(exc).splitlines()[0]}")
            failures += 1
            continue

        share = (
            response.reasoning_tokens / response.completion_tokens
            if response.completion_tokens
            else 0.0
        )
        print(f"text              {response.text!r}")
        print(f"provider version  {response.provider_version}")
        print(f"prompt tokens     {response.prompt_tokens}")
        print(f"completion tokens {response.completion_tokens}")
        print(f"  of which reasoning {response.reasoning_tokens} ({share:.0%})")
        print(f"  visible            {response.visible_tokens}")
        print(f"incomplete        {response.incomplete}")

        if response.incomplete:
            print("  NOTE: the output budget ran out. Tokens were billed, no answer came.")

    print(
        "\nRecord the provider versions above in the run manifest, and the reasoning "
        "share in the overhead study.\nNeither is a target: FR66's thresholds are "
        "still yours to set."
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
