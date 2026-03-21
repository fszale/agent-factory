from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from agent_factory.registry import TwinPackage
from agent_factory.runtime import TwinRuntime


@dataclass(slots=True)
class SmokeResult:
    case_name: str
    passed: bool
    details: str


def run_smoke_suite(runtime: TwinRuntime, twin: TwinPackage) -> list[SmokeResult]:
    smoke_file = twin.manifest.evals.smoke_file
    if not smoke_file:
        return []

    raw = yaml.safe_load((twin.base_dir / smoke_file).read_text(encoding="utf-8"))
    results: list[SmokeResult] = []
    for case in raw.get("cases", []):
        response = runtime.chat(
            twin_id=twin.manifest.twin_id,
            user_message=case["message"],
            model_profile=case.get("model_profile"),
            top_k=case.get("top_k", 3),
        )
        lowered_text = response.text.lower()
        missing = [
            keyword
            for keyword in case.get("expected_keywords", [])
            if keyword.lower() not in lowered_text
        ]
        passed = not missing
        details = "ok" if passed else f"missing expected keywords: {', '.join(missing)}"
        results.append(SmokeResult(case_name=case["name"], passed=passed, details=details))
    return results
