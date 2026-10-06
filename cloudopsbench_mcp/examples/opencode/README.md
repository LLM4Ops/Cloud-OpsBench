# OpenCode connection example

Start either system's server using the [MCP README](../../README.md).
Configure the task model and authentication in OpenCode as usual.

Merge [opencode.json](opencode.json) into the configuration of a separate agent
workspace, outside the benchmark checkout. If the workspace has no configuration,
copy the example there as `opencode.json`. It uses the OpenCode 1.x configuration
format used with v1.18.31. Change the URL if using another port.

From that workspace, check the connection:

```bash
opencode mcp list
```

Launch a fresh OpenCode session and supply the incident query and namespace.
The running server determines the active case and the system's tool catalog;
no client configuration change is needed to switch between Boutique and
TrainTicket. Restart the server and begin a new session for each case.

This example registers the diagnostic interface only. It does not configure
Skills, a model provider, a diagnostic budget, or a batch evaluator.

Reference: [OpenCode MCP documentation](https://opencode.ai/docs/mcp-servers/).
