# AWS Agent ablation benchmark

This benchmark compares a small local model in OpenCode under six controlled conditions:

1. baseline
2. official AWS deploy skill
3. official AWS Knowledge MCP
4. skill + Knowledge MCP
5. frozen public unit-price MCP
6. skill + frozen public unit-price MCP

The official AWS Pricing MCP is probed separately without credentials. The local price MCP exists only to isolate the value of structured price lookup without leaking oracle totals.
