.PHONY: install lint typecheck test validate smoke report check

install:
	python -m pip install -e '.[dev]'

lint:
	ruff check .

typecheck:
	mypy src

test:
	pytest

validate:
	aws-agent-eval validate --dataset datasets/aws-cost-v1
	aws-agent-eval validate --dataset datasets/aws-official-solutions-v1

smoke:
	rm -rf runs/smoke
	aws-agent-eval experiment --dataset datasets/aws-cost-v1 --profile config/profiles/mock.json --repetitions 1 --run-dir runs/smoke/general
	aws-agent-eval experiment --dataset datasets/aws-official-solutions-v1 --profile config/profiles/mock.json --repetitions 3 --run-dir runs/smoke/official

report:
	aws-agent-eval report --run-dir runs/smoke/general
	aws-agent-eval report --run-dir runs/smoke/official

check: lint typecheck test validate smoke report
