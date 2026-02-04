# Security Policy

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, please email security@flavcliq.com with:

- Description of the vulnerability
- Steps to reproduce (if applicable)
- Potential impact
- Suggested fix (if you have one)

We aim to acknowledge reports within 48 hours and provide a timeline for a fix.

## Security Best Practices

When using BiteGraph:

- Keep dependencies up to date (`pip install --upgrade -e ".[dev]"`)
- Store sensitive data (raw emails, keys) encrypted at rest
- Use HTTPS when transmitting order data
- Regularly audit access logs
- Follow the privacy policies outlined in `docs/privacy.md`

## Supported Versions

Security updates are provided for the latest release. Please upgrade promptly.

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |
