# Evaluations

## Overview

The project includes a custom evaluation harness in `/Users/sameet/Documents/Projects/applygraph/evals`.

It is framework-free and tailored to the streamed chat workflow.

## What It Covers

- request routing correctness
- required output-key checks
- forbidden/required term checks
- per-case scoring
- baseline comparison
- category summaries
- optional LLM-as-judge scoring

Current categories include:

- `analyze_job`
- `tailor_resume`
- `draft_message`
- `guardrail`

## Main Files

- `/Users/sameet/Documents/Projects/applygraph/evals/run_evals.py`
- `/Users/sameet/Documents/Projects/applygraph/evals/judge.py`
- `/Users/sameet/Documents/Projects/applygraph/evals/cases/`
- `/Users/sameet/Documents/Projects/applygraph/evals/baselines/latest.json`
- `/Users/sameet/Documents/Projects/applygraph/evals/reports/latest.json`

## Case Format

Example structure:

```json
{
  "name": "analyze_job_fastapi_fit",
  "category": "analyze_job",
  "input": {
    "message": "Analyze this role..."
  },
  "expected": {
    "request_type": "analyze_job",
    "required_output_keys": ["response"],
    "required_terms": ["fastapi"],
    "forbidden_terms": ["sourdough"]
  },
  "rubric": "The response should ..."
}
```

## Run Locally

Deterministic evals only:

```bash
python evals/run_evals.py --skip-judge
```

With judge model:

```bash
EVAL_JUDGE_PROVIDER=openai \
EVAL_JUDGE_MODEL=gpt-4.1-mini \
EVAL_JUDGE_OPENAI_API_KEY=your-key \
python evals/run_evals.py
```

## Why This Matters

This is one of the strongest engineering features in the project because it turns prompt/workflow changes into something measurable instead of subjective.

It demonstrates:

- regression testing for LLM systems
- evaluation design
- optional judge-based scoring
- category-level quality tracking
