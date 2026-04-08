from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Prevent local eval runs from hanging on an absent collector when importing the app.
os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "")

from evals.judge import EvalJudge, JudgeResult


CASES_DIR = PROJECT_ROOT / "evals" / "cases"
BASELINE_PATH = PROJECT_ROOT / "evals" / "baselines" / "latest.json"
REPORTS_DIR = PROJECT_ROOT / "evals" / "reports"
DEFAULT_API_URL = "http://localhost:8000/chat/stream"


@dataclass
class DeterministicCheck:
    name: str
    passed: bool
    detail: str


@dataclass
class CaseResult:
    name: str
    category: str
    passed: bool
    deterministic_score: float
    total_score: float
    duration_ms: float
    request_type: str | None
    checks: list[DeterministicCheck]
    judge: dict[str, Any]
    output: dict[str, Any]
    regression: str | None = None


class LiveApiClient:
    def __init__(self, api_url: str) -> None:
        self._api_url = api_url

    def invoke(self, message: str) -> dict[str, Any]:
        response = httpx.post(
            self._api_url,
            json={"message": message},
            headers={"Accept": "text/event-stream"},
            timeout=120.0,
        )
        response.raise_for_status()
        return extract_final_sse_event(response.text)


class EmbeddedApiClient:
    def __init__(self) -> None:
        from fastapi.testclient import TestClient

        from backend.api import deps
        from backend.telemetry import metrics as telemetry_metrics
        from backend.telemetry import tracing as telemetry_tracing

        telemetry_tracing.setup_tracing = lambda app, settings: None
        telemetry_metrics.setup_metrics = lambda settings: None
        from backend.main import app

        self._app = app
        self._deps = deps
        self._app.dependency_overrides[self._deps.get_db_session] = lambda: None
        self._client = TestClient(self._app)

    def invoke(self, message: str) -> dict[str, Any]:
        response = self._client.post("/chat/stream", json={"message": message})
        response.raise_for_status()
        return extract_final_sse_event(response.text)

    def close(self) -> None:
        self._app.dependency_overrides.clear()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run custom regression evals for ApplyGraph")
    parser.add_argument("--api-url", default=None, help="Optional live backend URL for /chat/stream")
    parser.add_argument(
        "--cases-dir",
        default=str(CASES_DIR),
        help="Directory containing JSON eval case definitions",
    )
    parser.add_argument(
        "--baseline-path",
        default=str(BASELINE_PATH),
        help="JSON baseline file used for regression comparison",
    )
    parser.add_argument(
        "--report-path",
        default=None,
        help="Optional path for the JSON report. Defaults to evals/reports/latest.json",
    )
    parser.add_argument(
        "--regression-threshold",
        type=float,
        default=0.10,
        help="Fail if total_score drops by more than this amount relative to baseline",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Overwrite the baseline file with the current run summary",
    )
    parser.add_argument(
        "--skip-judge",
        action="store_true",
        help="Disable the optional LLM-as-judge scoring step",
    )
    return parser.parse_args()


def load_cases(cases_dir: Path) -> list[dict[str, Any]]:
    cases = []
    for path in sorted(cases_dir.glob("*.json")):
        with path.open() as handle:
            payload = json.load(handle)
        payload["_path"] = str(path)
        cases.append(payload)
    if not cases:
        raise ValueError(f"No eval cases found in {cases_dir}")
    return cases


def load_baseline(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open() as handle:
        return json.load(handle)


def extract_final_sse_event(body: str) -> dict[str, Any]:
    blocks = [block for block in body.strip().split("\n\n") if block.strip()]
    for block in reversed(blocks):
        data_lines = [line[5:].strip() for line in block.splitlines() if line.startswith("data:")]
        if not data_lines:
            continue
        payload = json.loads("\n".join(data_lines))
        if payload.get("type") == "final":
            return payload["data"]
    raise ValueError("No final SSE event found")


def run_deterministic_checks(case: dict[str, Any], result: dict[str, Any]) -> list[DeterministicCheck]:
    expected = case.get("expected", {})
    output = result.get("output", {})
    output_text = json.dumps(output, ensure_ascii=True).lower()
    checks: list[DeterministicCheck] = []

    expected_request_type = expected.get("request_type")
    actual_request_type = result.get("request_type")
    checks.append(
        DeterministicCheck(
            name="request_type",
            passed=actual_request_type == expected_request_type,
            detail=f"expected={expected_request_type}, actual={actual_request_type}",
        )
    )

    for key in expected.get("required_output_keys", []):
        checks.append(
            DeterministicCheck(
                name=f"has_key:{key}",
                passed=key in output,
                detail=f"output contains key '{key}'",
            )
        )

    for term in expected.get("required_terms", []):
        checks.append(
            DeterministicCheck(
                name=f"required_term:{term}",
                passed=term.lower() in output_text,
                detail=f"output should mention '{term}'",
            )
        )

    for term in expected.get("forbidden_terms", []):
        checks.append(
            DeterministicCheck(
                name=f"forbidden_term:{term}",
                passed=term.lower() not in output_text,
                detail=f"output should not mention '{term}'",
            )
        )

    if actual_request_type == "rejected":
        message = output.get("message", "")
        checks.append(
            DeterministicCheck(
                name="rejection_message_non_empty",
                passed=bool(message.strip()),
                detail="guardrail responses should include a message",
            )
        )

    return checks


def summarize_case(
    case: dict[str, Any],
    result: dict[str, Any],
    checks: list[DeterministicCheck],
    judge_result: JudgeResult,
    duration_ms: float,
    baseline: dict[str, Any],
    regression_threshold: float,
) -> CaseResult:
    passed_checks = sum(1 for check in checks if check.passed)
    deterministic_score = passed_checks / len(checks) if checks else 0.0
    if judge_result.available and judge_result.score is not None:
        judge_score = judge_result.score / 5.0
        total_score = (0.6 * deterministic_score) + (0.4 * judge_score)
        judge_pass = bool(judge_result.passed)
    else:
        total_score = deterministic_score
        judge_pass = True

    passed = deterministic_score == 1.0 and judge_pass
    regression = compare_with_baseline(
        case_name=case["name"],
        total_score=total_score,
        passed=passed,
        baseline=baseline,
        threshold=regression_threshold,
    )

    return CaseResult(
        name=case["name"],
        category=case.get("category", "uncategorized"),
        passed=passed,
        deterministic_score=round(deterministic_score, 4),
        total_score=round(total_score, 4),
        duration_ms=round(duration_ms, 2),
        request_type=result.get("request_type"),
        checks=checks,
        judge={
            "available": judge_result.available,
            "score": judge_result.score,
            "passed": judge_result.passed,
            "summary": judge_result.summary,
            "raw_response": judge_result.raw_response,
        },
        output=result,
        regression=regression,
    )


def compare_with_baseline(
    *,
    case_name: str,
    total_score: float,
    passed: bool,
    baseline: dict[str, Any],
    threshold: float,
) -> str | None:
    previous = baseline.get(case_name)
    if not previous:
        return None
    previous_score = float(previous.get("total_score", 0.0))
    previous_passed = bool(previous.get("passed", False))
    if previous_passed and not passed:
        return "previously passed but now failing"
    if total_score < previous_score - threshold:
        return f"score dropped from {previous_score:.2f} to {total_score:.2f}"
    return None


def build_report(results: list[CaseResult], started_at: datetime) -> dict[str, Any]:
    pass_count = sum(1 for result in results if result.passed)
    average_score = sum(result.total_score for result in results) / len(results)
    category_summary: dict[str, Any] = {}
    for result in results:
        bucket = category_summary.setdefault(
            result.category,
            {"cases": 0, "passed": 0, "failed": 0, "average_score": 0.0},
        )
        bucket["cases"] += 1
        bucket["passed"] += int(result.passed)
        bucket["failed"] += int(not result.passed)
        bucket["average_score"] += result.total_score
    for bucket in category_summary.values():
        bucket["average_score"] = round(bucket["average_score"] / bucket["cases"], 4)
    return {
        "timestamp": started_at.isoformat(),
        "summary": {
            "cases": len(results),
            "passed": pass_count,
            "failed": len(results) - pass_count,
            "average_score": round(average_score, 4),
            "regressions": [result.name for result in results if result.regression],
            "categories": category_summary,
        },
        "results": [
            {
                **asdict(result),
                "checks": [asdict(check) for check in result.checks],
            }
            for result in results
        ],
    }


def write_report(report: dict[str, Any], report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w") as handle:
        json.dump(report, handle, indent=2)


def update_baseline(results: list[CaseResult], baseline_path: Path) -> None:
    baseline_payload = {
        result.name: {
            "passed": result.passed,
            "total_score": result.total_score,
            "request_type": result.request_type,
        }
        for result in results
    }
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    with baseline_path.open("w") as handle:
        json.dump(baseline_payload, handle, indent=2)


async def run_judge_if_enabled(
    judge: EvalJudge | None,
    case: dict[str, Any],
    result: dict[str, Any],
) -> JudgeResult:
    if judge is None:
        return JudgeResult(
            available=False,
            score=None,
            passed=None,
            summary="LLM judge skipped by configuration.",
        )
    return await judge.score_case(
        case_name=case["name"],
        message=case["input"]["message"],
        rubric=case.get("rubric", ""),
        output=result,
    )


def print_summary(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print("\nEval summary")
    print(f"- Cases: {summary['cases']}")
    print(f"- Passed: {summary['passed']}")
    print(f"- Failed: {summary['failed']}")
    print(f"- Average score: {summary['average_score']}")
    if summary["regressions"]:
        print(f"- Regressions: {', '.join(summary['regressions'])}")
    if summary["categories"]:
        print("- Categories:")
        for category, category_summary in sorted(summary["categories"].items()):
            print(
                "  "
                f"{category}: cases={category_summary['cases']}, "
                f"passed={category_summary['passed']}, "
                f"failed={category_summary['failed']}, "
                f"avg_score={category_summary['average_score']}"
            )

    for result in report["results"]:
        status = "PASS" if result["passed"] else "FAIL"
        regression = f" | regression: {result['regression']}" if result["regression"] else ""
        print(
            f"  - {status} {result['name']} [{result['category']}] "
            f"(score={result['total_score']:.2f}, route={result['request_type']}, latency={result['duration_ms']}ms){regression}"
        )


def main() -> int:
    args = parse_args()
    started_at = datetime.now(UTC)
    cases = load_cases(Path(args.cases_dir))
    baseline = load_baseline(Path(args.baseline_path))
    report_path = Path(args.report_path) if args.report_path else REPORTS_DIR / "latest.json"

    client = LiveApiClient(args.api_url) if args.api_url else EmbeddedApiClient()
    judge = None if args.skip_judge else EvalJudge()

    results: list[CaseResult] = []
    try:
        for case in cases:
            start = time.perf_counter()
            final_result = client.invoke(case["input"]["message"])
            duration_ms = (time.perf_counter() - start) * 1000
            checks = run_deterministic_checks(case, final_result)
            judge_result = asyncio.run(run_judge_if_enabled(judge, case, final_result))
            results.append(
                summarize_case(
                    case,
                    final_result,
                    checks,
                    judge_result,
                    duration_ms,
                    baseline,
                    args.regression_threshold,
                )
            )
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()

    report = build_report(results, started_at)
    write_report(report, report_path)
    if args.update_baseline:
        update_baseline(results, Path(args.baseline_path))

    print_summary(report)
    regressions = any(result.regression for result in results)
    failures = any(not result.passed for result in results)
    return 1 if regressions or failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
