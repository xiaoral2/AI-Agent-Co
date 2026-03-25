# Security

If you believe you have found a security vulnerability in this repository, please **do not** open a public issue.

Instead, report it privately to the repository maintainers (for example via GitHub **Security advisories** for the repo, if enabled, or direct contact if you maintain a fork).

Include enough detail to reproduce the issue (version, configuration, minimal steps) without posting secrets or live API keys.

This project orchestrates LLM calls and subprocesses (e.g. `git`, `pytest`). Treat mission text and workspace paths as **untrusted input** when exposing the harness to a network or multi-tenant environment.
