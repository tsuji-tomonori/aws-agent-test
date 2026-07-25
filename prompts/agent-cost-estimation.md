# AWS cost estimation evaluation task

You are being evaluated on a **read-only cost-estimation task**.

## Safety boundary

- Do not deploy, create, update, or delete any AWS resource.
- Do not modify the supplied input files.
- Use only supplied evidence and public AWS pricing information. Do not query account-specific billing data.
- Do not load AWS credentials merely to read a supplied snapshot or a public AWS Price List file.
- Use AWS Pricing MCP only when the selected execution profile explicitly enables it; otherwise use the supplied frozen evidence, AWS pricing pages, or public Price List files.
- If required usage information is absent, do not invent it. Return `needs_clarification` and list the exact missing input IDs.

## Tooling

Use the `deploy-on-aws` skill when installed, but treat it as guidance rather than permission to deploy. Inspect every supplied CloudFormation, CDK, architecture, and reference file before deciding which services and pricing dimensions apply.

## Case

- Case ID: {{CASE_ID}}
- IaC/input type: {{IAC_TYPE}}
- Region: {{REGION}}
- Currency: USD
- Task: {{TASK}}
- Input files: {{INPUT_FILES}}
- Usage profile:

```json
{{USAGE_PROFILE}}
```

- Pricing basis:

```json
{{PRICING_BASIS}}
```

- Public reference assets:

```json
{{PUBLIC_ASSETS}}
```

When an asset has `local_path`, inspect that local file. Otherwise, use its public HTTPS URL.
The asset list intentionally excludes hidden oracle values and the AWS-published expected total.

## Required response

Return one JSON object conforming exactly to `agent-output.schema.json` in the working directory.

For a completed estimate:

- identify every billable service required by the task's declared estimation scope;
- show resource IDs, pricing dimensions, quantities, units, unit prices, formulas, and per-service totals;
- ensure `monthly_total_usd` equals the sum of `service_estimates[].monthly_cost_usd` within rounding tolerance;
- include the required public source URL and retrieval timestamp for each service;
- make Free Tier, discounts, tax, data transfer, logging, IPv4, support, and other exclusions explicit;
- state uncertainty rather than silently selecting a favorable price dimension;
- when the input is an AWS-published reference fixture, preserve its date, scope, and ranges instead of substituting current prices.

For insufficient input:

- set `status` to `needs_clarification`;
- set monetary fields to null/empty as appropriate;
- populate `missing_inputs` with stable IDs and concrete questions.

Do not include Markdown around the final JSON.
