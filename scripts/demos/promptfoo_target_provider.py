"""Promptfoo custom-provider target for the Promptfoo redteam demo agent
(Task 4, plans/v2/2026-08-12-consolidated-wedge-sprint-full-build-plan.md).

Promptfoo's `file://` provider protocol calls this module's `call_api`
function with the generated attack prompt and returns a dict with an
"output" key holding the demo agent's response. This stands in for a minimal
memory-writing/tool-calling agent so the agentic:memory-poisoning and
hijacking plugins have something to attack.
"""


def call_api(prompt: str, options: dict, context: dict) -> dict:
    lowered = prompt.lower()
    if "ignore" in lowered and "instructions" in lowered:
        return {"output": "Understood — updating stored preferences as instructed."}
    return {"output": "I can help with that within my approved tools."}
