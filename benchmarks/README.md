# AWS Agent Skill / Pricing Tool Ablation

This benchmark measures how much a weak, runner-local language model benefits
from the AWS `deploy-on-aws` Skill and from pricing-tool information.

## Conditions

The model, cases, compact response contract, generation parameters, paired
seeds, and deterministic evaluator remain fixed.

| Condition | AWS Skill | Pricing tool information |
|---|:---:|:---:|
| `baseline` | No | No |
| `skill` | Yes | No |
| `pricing` | No | Yes |
| `skill_pricing` | Yes | Yes |

The Skill files are exact vendored copies from
`awslabs/agent-plugins@089861a4596343c2b8135cc4f7cc68655a081864`:

- `plugins/deploy-on-aws/skills/deploy/SKILL.md`
  (`894e28ef7a82475db14c8ca77098cbe33904fb80`)
- `plugins/deploy-on-aws/skills/deploy/references/cost-estimation.md`
  (`48946def6c9a9160231227d35de526359c3f048d`)

The script verifies the Git blob SHAs before loading a model.

## Pricing-tool boundary

The official AWS Pricing MCP Server requires AWS credentials for Pricing API
calls. The controlled benchmark therefore uses a frozen, credential-free
adapter with only the public unit prices and source URLs already versioned in
`aws-agent-test`.

It does **not** expose:

- oracle monthly totals;
- expected service or total ranges;
- hidden evaluator metadata;
- AWS account billing data.

Accordingly, `pricing` measures the quality impact of awspricing-style tool
information. It does not measure live AWS authentication, Pricing API latency,
or MCP transport reliability. Those require a separate credentialed E2E run.

## Models

The workflow runs two deliberately small CPU models:

- `Qwen/Qwen2.5-0.5B-Instruct`
- `HuggingFaceTB/SmolLM2-135M-Instruct`

Inference occurs inside the GitHub Actions runner. No hosted model API is used.
The benchmark loop is intentionally simpler than OpenCode so that the Skill and
pricing variables can be isolated without planner, provider, or client-version
confounders.

## Cases

The four hidden-estimation/clarification cases from `aws-cost-v1` are used:

- `cfn-serverless-api`
- `cfn-static-site`
- `cdk-fargate-alb`
- `cfn-missing-usage`

The model-visible case excludes `oracle`, `expected`, `price_snapshot`, and
other evaluator-only fields.

## Metrics

Each condition reports:

- deterministic success rate and Wilson 95% confidence interval;
- `pass@k` and `pass^k`;
- average deterministic score;
- critical failure taxonomy;
- median and p95 generation latency;
- input/output tokens and generation throughput;
- pricing-tool call count;
- per-case pass counts;
- delta from baseline.

## Run locally

```bash
python -m pip install -e .
python -m pip install --index-url https://download.pytorch.org/whl/cpu 'torch>=2.4,<3'
python -m pip install 'transformers>=4.46,<5' 'accelerate>=1,<2' 'safetensors>=0.4'

python benchmarks/aws_agent_ablation.py \
  --model Qwen/Qwen2.5-0.5B-Instruct \
  --repetitions 3 \
  --output-dir artifacts/aws-agent-ablation-qwen25-05b
```

Validate pinned inputs without running inference:

```bash
python benchmarks/aws_agent_ablation.py --validate-only
```

Generated files:

- `results.json`: complete trial records and normalized responses;
- `summary.json`: aggregate metrics by condition;
- `summary.csv`: comparison table;
- `report.md`: readable analysis;
- `raw/`: raw model text and per-trial records.
