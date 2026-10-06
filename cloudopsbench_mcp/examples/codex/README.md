# Codex connection example

Start either system's server using the [MCP README](../../README.md).
Configure the task model and authentication in Codex as usual.

Register the already-running HTTP server:

```bash
codex mcp add cloudopsbench --url http://127.0.0.1:8000/mcp
codex mcp list
```

Alternatively, merge [config.toml](config.toml) into the Codex configuration
used for this run. Use one registration method; do not replace your entire
existing configuration with this snippet. Change the URL if using another port.

Launch a fresh Codex session from a separate agent workspace, outside the
benchmark checkout, and supply the incident query and namespace. The same
configuration supports Boutique and TrainTicket; the running server determines
the tools and active case. Start a fresh session for each case.

This example registers the diagnostic interface only. It does not configure
Skills, a model provider, a diagnostic budget, or a batch evaluator. The
configuration follows the interface used with Codex CLI v0.139.0.

Reference: [Codex MCP documentation](https://developers.openai.com/codex/mcp/).
