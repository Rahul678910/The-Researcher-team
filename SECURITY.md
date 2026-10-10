# Security Policy

The Researcher is a Python verification runner that sends HTTP requests to a target application and checks its API responses. This policy explains how to report security issues responsibly.

## Supported versions

Security reports are welcome for the latest version on the repository's default branch. Older copies may not receive fixes; please verify an issue against the latest version before reporting it, when safe to do so.

## Reporting a vulnerability

**Please do not disclose suspected vulnerabilities in public issues, pull requests, discussions, or social media before the maintainer has had a chance to review them.**

1. Open the repository's **Security** tab and use **Report a vulnerability** / a private GitHub Security Advisory, if that feature is enabled.
2. If private vulnerability reporting is unavailable, contact the repository maintainer privately through a contact method listed on their GitHub profile. Do not include exploit details in a public issue.
3. If possible, include the affected version or commit, environment, concise reproduction steps, expected and actual behavior, potential impact, and any relevant logs with secrets and personal information removed.

You will receive a response as soon as reasonably possible. Please understand that response and remediation timelines are not guaranteed. The maintainer may ask for more information to reproduce or assess the issue.

## Scope

Examples of issues worth reporting include:

- Unintended disclosure of secrets or sensitive data caused by this project.
- Unsafe handling of untrusted HTTP responses or input that could affect the machine running the verifier.
- A vulnerability in the runner's local server-startup or request-handling behavior.
- A dependency or configuration issue with a demonstrable security impact on this project.

The verifier is designed to send requests to the configured target URL. Only test systems you own or have explicit permission to assess. Do not perform denial-of-service testing, access other people's data, or test third-party services without authorization.

## What to include—and what to avoid

Please provide enough detail to reproduce the issue safely. Use a minimal proof of concept where possible. Do not send real credentials, API keys, private keys, session cookies, personal data, or production datasets. Redact sensitive values from screenshots and logs.

Do not attempt to exploit an issue beyond what is necessary to demonstrate its impact, and do not modify or delete data that belongs to others.

## Secrets and repository hygiene

Never commit API keys, access tokens, passwords, private keys, `.env` files, personal data, or production logs. The repository's `.gitignore` helps exclude common local files, but it does not replace reviewing staged changes or using secret scanning.

If a secret is committed, revoke or rotate it immediately. Removing it in a later commit does not invalidate copies in repository history; follow GitHub's guidance for removing sensitive data from history if needed.

## Disclosure

Please allow the maintainer reasonable time to investigate and address a reported issue before making technical details public. Coordinated disclosure is appreciated, but no specific disclosure deadline or bounty is promised by this policy.
