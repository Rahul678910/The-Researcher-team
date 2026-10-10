<div align="center">

# ⚡ The Researcher
### Automated API Verification Runner

**Put your research API through its paces.**  
Validate generated briefs, challenge error handling, and check essential service behavior with one Python command.

<p>
  <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white" alt="Python 3.9+" />
  <img src="https://img.shields.io/badge/Dependencies-Standard%20Library-2E8B57" alt="Standard library only" />
  <img src="https://img.shields.io/badge/Checks-19-7C3AED" alt="19 checks" />
  <img src="https://img.shields.io/badge/Output-Terminal%20%7C%20JSON-0F766E" alt="Terminal and JSON output" />
</p>

[Quick Start](#-quick-start) · [Test Matrix](#-the-four-test-tiers) · [CLI Options](#-command-line-options) · [API Contract](#-expected-api-contract) · [Troubleshooting](#-troubleshooting)

</div>

---

## 🧭 What is it?

**The Researcher Verification Runner** is a lightweight, standalone test harness for The Researcher HTTP API. It sends representative requests to the service and checks whether responses, error codes, and generated research briefs match the expectations encoded in the test suite.

Run it against an existing local server, point it at another test instance, or let it attempt to start the project server locally.

### Why use it?

- **No test-framework setup:** the runner uses Python's standard library.
- **Schema-aware checks:** verifies required fields and key data types in research briefs.
- **Negative-path coverage:** tests malformed requests and expected HTTP errors.
- **Concurrency smoke test:** sends five research requests at the same time.
- **Automation-friendly:** returns a non-zero exit code when verification fails and can emit JSON results.

> [!NOTE]
> The high-concurrency and low-latency cases verify that the API accepts demanding task descriptions and returns schema-valid briefs. They do **not** benchmark 50,000 real connections or prove a sub-5-ms response time.

## ✨ At a glance

| | |
|---|---|
| **19 checks** | Four tiers, from domain synthesis to end-to-end smoke checks |
| **4 synthesis domains** | Frontend, backend, data pipeline, and DevOps/cloud |
| **Standard library** | No third-party pip packages are imported by `verify.py` |
| **Two report formats** | Human-readable terminal table or machine-readable JSON |
| **Python** | 3.9+ |

## 🚀 Quick start

### 1. Check your Python version

```bash
python --version
```

Python **3.9 or newer** is required.

### 2. Place the runner in your project

A typical project layout looks like this:

```text
your-project/
├── verify.py
├── README.md
└── src/
    └── the_researcher/
        └── server.py
```

The runner adds the project root and `src/` to Python's import path. Your application may have additional files; the important part is that its server module and API routes match the expected contract.

### 3. Run the suite

```bash
python verify.py
```

By default, the runner checks `http://127.0.0.1:8000` for a healthy service. If one is not available, it attempts to start an in-process server on a free local port.

### 4. Verify a running server

```bash
python verify.py --url http://127.0.0.1:8000
```

Use `--url` to specify the base URL of your test server.

## 🧪 The four test tiers

| Tier | Focus | Checks | What it covers |
|---|---|---:|---|
| **1 — Domain synthesis** | Core functionality | 4 | Frontend, backend, data pipeline, and DevOps/cloud briefs; HTTP status, schema, and expected domain |
| **2 — Error handling** | Invalid input | 8 | Missing/blank task, invalid field types, empty body, malformed JSON, method not allowed, and unknown route |
| **3 — Demanding constraints** | Complex task descriptions | 3 | High-concurrency, ultra-low-latency, and offline-first requirements; response success and schema validity |
| **4 — Service checks** | End-to-end smoke tests | 4 | Health endpoint, HTML UI delivery, five parallel requests, and distinct output domains |
| | **Total** | **19** | |

### Test ID map

<details>
<summary><strong>View all test IDs</strong></summary>

| Tier | Test IDs |
|---|---|
| Tier 1 | `T1-FE-01`, `T1-BE-01`, `T1-DP-01`, `T1-DO-01` |
| Tier 2 | `T2-ERR-01` through `T2-ERR-08` |
| Tier 3 | `T3-CD-01` through `T3-CD-03` |
| Tier 4 | `T4-E2E-01` through `T4-E2E-04` |

</details>

## 🎛️ Command-line options

| Option | What it does |
|---|---|
| `--url URL` | Target server base URL. If omitted, checks localhost and may try to start the application server. |
| `--port PORT` | Local port to check when `--url` is omitted. Default: `8000`. |
| `--json` | Prints a machine-readable JSON report instead of the terminal table. |
| `--verbose`, `-v` | Accepted by the CLI; currently does not change the amount of diagnostic output. |
| `--help` | Displays command help. |

### Handy commands

```bash
# Run against the default local setup
python verify.py

# Check a different local port
python verify.py --port 9000

# Test a specific server
python verify.py --url http://127.0.0.1:8000

# Emit JSON for scripts or CI
python verify.py --json

# See all available options
python verify.py --help
```

## 🔌 Expected API contract

The runner expects the application to expose these routes:

| Method | Route | Expected behavior |
|---|---|---|
| `GET` | `/api/health` | HTTP `200`; JSON object containing a `status` field |
| `GET` | `/` | HTTP `200`; HTML content type and page text containing `The Researcher` |
| `POST` | `/api/research` | Accepts a JSON research task and returns a research brief |

Example request body:

```json
{
  "task": "Build a responsive analytics dashboard",
  "constraints": [
    "responsive UI",
    "interactive charts"
  ]
}
```

### Research brief validation

The response validator expects the following fields:

| Field | Requirement |
|---|---|
| `task` | Non-empty string |
| `domain` | Non-empty string |
| `approach` | Non-empty string or list; legacy `approaches` is also supported |
| `libraries` | Non-empty list; entries need version-like information |
| `documentation_links` | Non-empty list of HTTP/HTTPS URLs; legacy `documentation` is also supported |
| `pitfalls` | Non-empty list of descriptive strings or objects |

For object-style library entries, the validator checks `name` and `version`. For pitfall objects, it looks for text in `description`, `caveat`, `title`, or `mitigation`.

## 📊 Reading the results

### Terminal mode

The default report shows each test's tier, ID, name, duration, and status, followed by a summary.

- **Exit code `0`** — all registered tests passed.
- **Exit code `1`** — at least one test failed, or server startup/readiness failed.

ANSI colors are disabled when the `NO_COLOR` environment variable is set or standard output is not a terminal.

### JSON mode

```bash
python verify.py --json
```

The report includes `status`, `exit_code`, `total`, `passed`, `failed`, `schema_conformance_rate`, `duration_ms`, `target_url`, and per-test `results`. Startup errors are emitted as a separate JSON error object.

## 🛠️ Troubleshooting

<details>
<summary><strong>Server won't start</strong></summary>

- Confirm the application source is present and importable from the project root or `src/`.
- Check that `the_researcher.server` exposes one of the supported entry points: `create_server(host, port)`, `ResearcherServer(host, port)`, or `run_server(host=..., port=...)`.
- Read the exception printed by the runner for the underlying startup problem.

</details>

<details>
<summary><strong>Server readiness times out</strong></summary>

- Confirm `GET /api/health` returns HTTP `200`.
- The auto-start readiness check waits up to five seconds.
- If the app is already running, pass its URL with `--url`.

</details>

<details>
<summary><strong>A schema check fails</strong></summary>

- Inspect the failing test's detail in the terminal output or JSON report.
- Check all required fields and non-empty values.
- Ensure library entries include version-like information and documentation links use `http://` or `https://`.

</details>

<details>
<summary><strong>An endpoint returns an unexpected status</strong></summary>

Confirm the route, HTTP method, request validation, and any middleware or authentication settings match the expected API contract.

</details>

## 🔐 Security & scope

- Run tests against a development or test environment you own or are authorized to assess.
- The runner uses `127.0.0.1` for local server discovery and auto-start by default; this is a loopback address, not your public IP.
- The suite checks that documentation links look like HTTP/HTTPS URLs; it does not verify that the links are reachable.
- This is an HTTP verification and smoke-testing script, not a full load-testing, penetration-testing, or performance-profiling framework.
- The script attempts to shut down an auto-started server object if it provides `shutdown()` and `server_close()`.

For vulnerability reporting guidance, see [`SECURITY.md`](SECURITY.md) if your repository includes it.

## 🤝 Contributing

Contributions and focused improvements are welcome.

1. Create a branch for your change.
2. Give new checks unique test IDs and clear failure messages.
3. Run `python verify.py` against the intended application server.
4. Check `python verify.py --json` when validating structured output.
5. Include relevant test results in your pull request.

## 📄 License

No license is specified in the supplied Python file. Add a `LICENSE` file and update this section once you choose the terms under which others may use, modify, or redistribute the project.

---

<div align="center">

**Built to make API behavior easier to verify — one test run at a time.**

</div>
