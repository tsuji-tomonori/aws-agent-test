# AGENTS.md

## Repository purpose

This repository evaluates non-deterministic agents on AWS cost-estimation tasks derived from CloudFormation, AWS CDK, and official AWS architecture material. Standard tests and official-reference holdouts must remain safe to run without AWS credentials.

## Non-negotiable rules

- Never add a command that deploys, updates, or deletes AWS resources.
- Do not require AWS credentials for mock, CI, frozen-snapshot, official-public-asset, public-page, or public-offer-file workflows.
- Keep AWS Pricing MCP profiles explicit and separate; grant only `pricing:*` when they are used.
- Never place a hidden oracle, hidden expected range, or official cost-page URL in an agent workspace or prompt.
- Official-reference holdout cases may expose public diagrams, templates, and usage dimensions, but not the AWS-published answer used as oracle.
- Public reference-reproduction cases may include public published ranges, but must be tagged and must not be reported as hidden estimation accuracy.
- Keep objective checks deterministic. An LLM judge must not override a critical deterministic failure.
- Live model, AWS API, or external asset calls must remain opt-in and must not run in pull-request CI.
- Validate public asset scheme, host, redirect target, size, media type, path, and digest.
- Do not commit credentials, model transcripts containing secrets, generated `runs/`, or downloaded `asset-cache/` data.
- A dataset price or official asset change requires a dataset version bump and independent arithmetic review.

## Development commands

```bash
python -m pip install -e '.[dev]'
ruff check .
mypy src
pytest
aws-agent-eval validate --dataset datasets/aws-cost-v1
aws-agent-eval validate --dataset datasets/aws-official-solutions-v1
aws-agent-eval experiment --dataset datasets/aws-official-solutions-v1 --profile config/profiles/mock.json --repetitions 3 --run-dir runs/local
aws-agent-eval report --run-dir runs/local
```

## Code conventions

- Python 3.11+, strict type hints for public functions.
- Standard-library solutions are preferred; production dependencies must be justified.
- Every evaluation or security rule needs at least one positive and one negative test.
- Error messages must identify the case, trial, or failed contract.
