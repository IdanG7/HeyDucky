# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in HeyDucky, please report it privately.

**Do not open a public GitHub issue.**

Instead, email **security@heyducky.dev** (or use [GitHub's private vulnerability reporting](https://github.com/IdanG7/HeyDucky/security/advisories/new)) with:

- A description of the vulnerability
- Steps to reproduce
- Any potential impact

You should receive an acknowledgement within 48 hours. We will work with you to understand the issue and coordinate a fix before any public disclosure.

## Scope

Security issues we care about include:

- **API key exposure** — config files, logs, or error messages leaking secrets
- **Arbitrary code execution** — beyond the intended debugger/git tool functionality
- **Path traversal** — the file server or read_source tool accessing files outside the project root
- **Network exposure** — the remote agent or file server being exploitable by unauthorized clients

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Best Practices for Users

- Store your Anthropic API key in the `ANTHROPIC_API_KEY` environment variable rather than in the config file when possible.
- When using `ducky-remote`, run it on a trusted network. The DAP relay and file server do not authenticate connecting clients.
- Do not commit `~/.config/ducky/config.toml` to version control.
