# The Researcher — Automated Verification Runner

A standalone Python verification runner for **The Researcher** HTTP API. It exercises research-brief generation, request validation, error handling, service health, web UI delivery, concurrent requests, and output differentiation.

The runner uses Python's standard library for its HTTP client and test orchestration, so **the verification script itself has no third-party pip dependencies**. The application server it tests must still be available in the project.

## Features

- **19 automated checks** organized into four tiers.
- Validates generated research briefs against a required JSON schema.
- Tests expected HTTP error responses for invalid requests and routes.
- Checks health and root web UI endpoints.
- Exercises five simultaneous research requests.
- Supports readable terminal output and machine-readable JSON output.
- Can test an already-running server or attempt to start the project server locally.
- Returns an exit code suitable for scripts and CI workflows.

## Requirements

- Python **3.9 or newer**.
- The corresponding **The Researcher** application source code, including its server module.
- For local auto-start, the server must expose one of the supported entry points in `the_researcher.server`:
  - `create_server(host, port)`
  - `ResearcherServer(host, port)`
  - `run_server(host=..., port=...)`

No third-party packages are imported by `verify.py`.

## Project layout

The script adds both the project root and its `src/` directory to Python's import path. A typical layout is:

```text
your-project/
├── verify.py
├── README.md
└── src/
    └── the_researcher/
        └── server.py
```

Your actual project may contain additional application files. The important requirement is that the server module and its API routes match the endpoints expected by the tests.

## Quick start

### 1. Open a terminal in the project root

```bash
cd your-project
```

### 2. Run the verification suite

```bash
python verify.py
```

When no URL is supplied, the runner first checks `http://127.0.0.1:8000`. If a healthy server is not found there, it attempts to start an in-process server on a free local port.

### 3. Test a server that is already running

```bash
python verify.py --url http://127.0.0.1:8000
```

Replace the URL with the base URL of your test instance. The server should expose the routes described below.

## Command-line options

| Option | Description |
|---|---|
| `--url URL` | Base URL of the HTTP server to test. If omitted, the runner checks localhost and may attempt to start the application server. |
| `--port PORT` | Local port to check when `--url` is omitted. Defaults to `8000`. |
| `--json` | Print a JSON report instead of the formatted terminal table. |
| `--verbose`, `-v` | Accepted as a detailed-diagnostics option by the CLI. In the current implementation, this flag does not change the report output. |
| `--help` | Display available command-line options. |

Examples:

```bash
# Default behavior
python verify.py

# Check a local server on port 9000
python verify.py --port 9000

# Check a specified server
python verify.py --url http://127.0.0.1:8000

# Produce machine-readable results
python verify.py --json

# Show command help
python verify.py --help
```

## Verification tiers

### Tier 1 — Domain synthesis (4 tests)

Checks that the API can generate a valid research brief for four task domains:

- Frontend / UI
- Backend / API
- Data pipelines
- DevOps / cloud

Each test expects HTTP `200`, validates the returned brief's schema, and checks that the returned `domain` matches an accepted value for that test.

### Tier 2 — Input validation and HTTP errors (8 tests)

Checks that the API handles invalid requests appropriately:

- Missing `task`
- Empty or whitespace-only `task`
- Invalid `task` type
- Invalid `constraints` type
- Empty request body
- Malformed JSON
- Unsupported HTTP method
- Nonexistent route

The tests expect `400` or `422` for invalid request payloads, `405` for a method not allowed, and `404` for a missing route.

### Tier 3 — Demanding task constraints (3 tests)

Submits research tasks describing:

- High concurrency (50,000 open sockets)
- Ultra-low latency (less than 5 ms at p99)
- Offline-first progressive web application behavior

These tests verify successful API responses and research-brief schema conformance. They **do not independently benchmark** 50,000 live connections, measure actual sub-5-ms latency, or validate a deployed offline-first application.

### Tier 4 — Service and end-to-end behavior (4 tests)

Checks:

- `GET /api/health` returns HTTP `200` with a JSON object containing `status`.
- `GET /` returns HTTP `200`, an HTML content type, and page content containing `The Researcher`.
- Five research requests can be submitted concurrently and return valid briefs.
- Two different research tasks produce different `domain` values.

## Expected API contract

The verification runner expects these endpoints:

| Method | Endpoint | Expected behavior |
|---|---|---|
| `GET` | `/api/health` | Returns HTTP `200` and JSON containing a `status` field. |
| `GET` | `/` | Returns HTTP `200` and HTML containing `The Researcher`. |
| `POST` | `/api/research` | Accepts a JSON research task and returns a research brief. |

A typical valid request used by the tests has this shape:

```json
{
  "task": "Build a responsive analytics dashboard",
  "constraints": [
    "responsive UI",
    "interactive charts"
  ]
}
```

The brief validator expects these required fields:

- `task` — a non-empty string.
- `domain` — a non-empty string.
- `approach` — a non-empty string or list, with compatibility handling for `approaches`.
- `libraries` — a non-empty list. Library entries must include explicit version-like information.
- `documentation_links` — a non-empty list of HTTP or HTTPS URLs, with compatibility handling for `documentation`.
- `pitfalls` — a non-empty list of descriptive strings or objects.

For object-style library entries, the validator checks `name` and `version`. For pitfalls, it looks for descriptive text such as `description`, `caveat`, `title`, or `mitigation`.

## Output and exit codes

### Terminal report

The default output is a table containing the tier, test ID, test name, duration, and pass/fail status. The summary includes the total, passed and failed tests, pass rate, and overall duration.

- Exit code `0`: every registered test passed.
- Exit code `1`: one or more tests failed, or the runner could not start or reach the server.

ANSI colors are disabled when `NO_COLOR` is set or standard output is not a terminal.

### JSON report

Run:

```bash
python verify.py --json
```

The JSON output includes:

- `status`
- `exit_code`
- `total`, `passed`, and `failed`
- `schema_conformance_rate`
- `duration_ms`
- `target_url`
- `results`, with each test's tier, ID, name, status, duration, and detail

This output is useful for automation and CI systems. Note that startup errors are emitted as a separate JSON object with an error status and exit code.

## Test IDs

| Tier | Test IDs |
|---|---|
| Tier 1 | `T1-FE-01`, `T1-BE-01`, `T1-DP-01`, `T1-DO-01` |
| Tier 2 | `T2-ERR-01` through `T2-ERR-08` |
| Tier 3 | `T3-CD-01` through `T3-CD-03` |
| Tier 4 | `T4-E2E-01` through `T4-E2E-04` |

## Troubleshooting

**The runner cannot launch the server**

- Confirm that the application source is present and importable from the project root or `src/`.
- Confirm that `the_researcher.server` provides one of the supported server entry points.
- Check the exception printed by the runner for the underlying import or startup problem.

**The server does not become ready**

- Confirm the server starts successfully and serves `GET /api/health`.
- The auto-start readiness check waits up to five seconds.
- If the application is already running, pass its URL with `--url`.

**A test fails with a schema error**

- Inspect the failed test's detail in the terminal report or JSON output.
- Confirm all required brief fields are present and non-empty.
- Ensure libraries include version-like information and documentation links use `http://` or `https://`.

**A request returns an unexpected status**

- Confirm the application implements `POST /api/research` and the expected validation behavior.
- Check whether middleware, authentication, or other local configuration changes the API response.

## Scope and limitations

- This is an HTTP-level verification runner, not a full load-testing or performance-profiling framework.
- The high-concurrency and latency tests submit descriptive tasks; they do not generate the stated workload against a live service.
- The suite checks the presence and shape of documentation links, not whether those links are reachable.
- The brief validator supports a few legacy field aliases (`documentation` and `approaches`).
- The `--verbose` option is parsed, but it currently does not enable additional diagnostic output.
- The script attempts to shut down an auto-started server object when that object supports `shutdown()` and `server_close()`.

## Contributing

1. Create a branch for your change.
2. Keep tests focused and give new checks a unique test ID.
3. Run `python verify.py` against the intended application server.
4. Check `python verify.py --json` if you need to inspect or process structured results.
5. Include relevant test results in your pull request.

## License

No license information is specified in `verify.py`. Add a `LICENSE` file and update this section to state the project's actual license before publishing or redistributing it.
