#!/usr/bin/env python3
"""
The Researcher - Automated Standalone Verification Runner
=========================================================
Executes the comprehensive Tier 1–4 opaque-box verification battery.
ZERO external pip dependencies: runs with standard Python 3.9+ libraries.

Usage:
    python verify.py
    python verify.py --url http://127.0.0.1:8000
    python verify.py --json
    python verify.py --verbose
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import http.client
import json
import os
import re
import socket
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import urllib.error
import urllib.parse
import urllib.request

# Ensure project root and src/ are in sys.path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# ANSI terminal formatting codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
DIM = "\033[2m"

# Disable colors if NO_COLOR environment variable is present or stdout not a tty
if os.environ.get("NO_COLOR") or not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
    RESET = ""
    BOLD = ""
    GREEN = ""
    RED = ""
    YELLOW = ""
    CYAN = ""
    MAGENTA = ""
    DIM = ""

VERSION_REGEX = re.compile(r"([><=~^@:]|\b\d+\.\d+)")


# ============================================================================
# HTTP Client Wrapper (Standard Library Only)
# ============================================================================

class StandaloneResponse:
    def __init__(self, status_code: int, headers: Dict[str, str], body: bytes):
        self.status_code = int(status_code)
        self.headers = {k.lower(): v for k, v in headers.items()}
        self.content = body
        self._text: Optional[str] = None

    @property
    def text(self) -> str:
        if self._text is None:
            try:
                self._text = self.content.decode("utf-8")
            except UnicodeDecodeError:
                self._text = self.content.decode("latin1", errors="replace")
        return self._text

    def json(self) -> Any:
        return json.loads(self.text)


class StandaloneClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def request(
        self,
        method: str,
        path: str,
        body: Optional[Union[bytes, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 12.0,
    ) -> StandaloneResponse:
        if not path.startswith("/"):
            path = "/" + path
        url = self.base_url + path

        req_headers = {"User-Agent": "TheResearcher-VerifyRunner/1.0"}
        if headers:
            req_headers.update(headers)

        body_bytes: Optional[bytes] = None
        if body is not None:
            if isinstance(body, bytes):
                body_bytes = body
            else:
                body_bytes = str(body).encode("utf-8")

        req = urllib.request.Request(url, data=body_bytes, headers=req_headers, method=method.upper())

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return StandaloneResponse(resp.status, dict(resp.headers), resp.read())
        except urllib.error.HTTPError as err:
            return StandaloneResponse(err.code, dict(err.headers), err.read())
        except Exception as err:
            raise RuntimeError(f"Connection to {url} failed: {err}")

    def get(self, path: str, headers: Optional[Dict[str, str]] = None) -> StandaloneResponse:
        return self.request("GET", path, headers=headers)

    def post(self, path: str, json_data: Any = None, headers: Optional[Dict[str, str]] = None) -> StandaloneResponse:
        req_headers = dict(headers or {})
        body = None
        if json_data is not None:
            body = json.dumps(json_data)
            req_headers.setdefault("Content-Type", "application/json")
        return self.request("POST", path, body=body, headers=req_headers)

    def post_raw(self, path: str, raw_body: Union[bytes, str], content_type: str = "application/json") -> StandaloneResponse:
        return self.request("POST", path, body=raw_body, headers={"Content-Type": content_type})


# ============================================================================
# Schema Validation Logic
# ============================================================================

def validate_brief_schema(brief: Any) -> List[str]:
    """Validates 100% deep schema conformance for Research Brief."""
    errors: List[str] = []
    if not isinstance(brief, dict):
        return [f"Root must be a JSON object (dict), got {type(brief).__name__}"]

    required_keys = ["task", "domain", "approach", "libraries", "documentation_links", "pitfalls"]
    for k in required_keys:
        if k not in brief:
            if k == "documentation_links" and "documentation" in brief:
                continue
            if k == "approach" and "approaches" in brief:
                continue
            errors.append(f"Missing required key: '{k}'")
        elif brief[k] is None:
            errors.append(f"Field '{k}' cannot be None")

    if errors:
        return errors

    # Task
    task = brief.get("task")
    if not isinstance(task, str) or len(task.strip()) == 0:
        errors.append("'task' must be a non-empty string")

    # Domain
    domain = brief.get("domain")
    if not isinstance(domain, str) or len(domain.strip()) == 0:
        errors.append("'domain' must be a non-empty string")

    # Approach
    approach = brief.get("approach")
    approaches_alt = brief.get("approaches")
    if approach is not None:
        if isinstance(approach, str):
            if len(approach.strip()) == 0:
                errors.append("'approach' string cannot be empty")
        elif isinstance(approach, list):
            if len(approach) == 0:
                errors.append("'approach' list cannot be empty")
        else:
            errors.append("'approach' must be string or list")
    elif approaches_alt is not None:
        if not isinstance(approaches_alt, list) or len(approaches_alt) == 0:
            errors.append("'approaches' must be a non-empty list")

    # Libraries
    libs = brief.get("libraries")
    if not isinstance(libs, list) or len(libs) == 0:
        errors.append("'libraries' must be a non-empty list")
    else:
        for idx, lib in enumerate(libs):
            if isinstance(lib, dict):
                name = str(lib.get("name", "")).strip()
                v = str(lib.get("version", "")).strip()
                if not name:
                    errors.append(f"Library [{idx}] missing name")
                if not v or not VERSION_REGEX.search(v):
                    errors.append(f"Library [{idx}] '{name}' lacks explicit version pinning (got '{v}')")
            elif isinstance(lib, str):
                if not VERSION_REGEX.search(lib):
                    errors.append(f"Library string [{idx}] lacks explicit version pinning (got '{lib}')")
            else:
                errors.append(f"Library [{idx}] must be dict or str")

    # Documentation Links
    docs = brief.get("documentation_links") or brief.get("documentation")
    if not isinstance(docs, list) or len(docs) == 0:
        errors.append("'documentation_links' must be a non-empty list")
    else:
        for idx, doc in enumerate(docs):
            url = str(doc.get("url", "") if isinstance(doc, dict) else doc).strip()
            if not (url.startswith("http://") or url.startswith("https://")):
                errors.append(f"Doc link [{idx}] '{url}' must be a valid HTTP/HTTPS URL")

    # Pitfalls
    pitfalls = brief.get("pitfalls")
    if not isinstance(pitfalls, list) or len(pitfalls) == 0:
        errors.append("'pitfalls' must be a non-empty list")
    else:
        for idx, p in enumerate(pitfalls):
            if isinstance(p, dict):
                text = str(p.get("description") or p.get("caveat") or p.get("title") or p.get("mitigation") or "").strip()
                if not text:
                    errors.append(f"Pitfall [{idx}] lacks descriptive text or mitigation")
            elif isinstance(p, str):
                if not p.strip():
                    errors.append(f"Pitfall [{idx}] cannot be empty")
            else:
                errors.append(f"Pitfall [{idx}] must be dict or str")

    return errors


# ============================================================================
# Server Discovery & Ephemeral Lifecycle
# ============================================================================

def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def is_server_ready(base_url: str) -> bool:
    try:
        c = StandaloneClient(base_url)
        res = c.get("/api/health")
        return res.status_code == 200
    except Exception:
        return False


def start_ephemeral_server(port: int) -> Tuple[Any, threading.Thread]:
    """Starts server in background thread using src.the_researcher.server."""
    server_obj = None
    server_thread = None

    try:
        from the_researcher.server import create_server
        server_obj = create_server("127.0.0.1", port)
    except (ImportError, AttributeError):
        try:
            from the_researcher.server import ResearcherServer
            server_obj = ResearcherServer("127.0.0.1", port)
        except (ImportError, AttributeError):
            from the_researcher.server import run_server
            server_thread = threading.Thread(
                target=run_server,
                kwargs={"host": "127.0.0.1", "port": port},
                daemon=True,
            )
            server_thread.start()
            return None, server_thread

    if server_obj is not None:
        server_thread = threading.Thread(target=server_obj.serve_forever, daemon=True)
        server_thread.start()

    return server_obj, server_thread


# ============================================================================
# Verification Test Definitions (Tiers 1–4)
# ============================================================================

class TestResult:
    def __init__(self, tier: str, test_id: str, name: str, passed: bool, duration_ms: float, detail: str = ""):
        self.tier = tier
        self.test_id = test_id
        self.name = name
        self.passed = passed
        self.duration_ms = duration_ms
        self.detail = detail

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": self.tier,
            "id": self.test_id,
            "name": self.name,
            "passed": self.passed,
            "duration_ms": round(self.duration_ms, 2),
            "detail": self.detail,
        }


# --- Tier 1 Tests ---

def test_t1_frontend(client: StandaloneClient) -> Tuple[bool, str]:
    payload = {
        "task": "Build a responsive real-time analytics dashboard with interactive charts, dark mode, and state management",
        "constraints": ["browser: evergreen", "reactive updates", "charting", "responsive UI"],
    }
    resp = client.post("/api/research", json_data=payload)
    if resp.status_code != 200:
        return False, f"Expected 200, got {resp.status_code}: {resp.text}"
    brief = resp.json()
    errs = validate_brief_schema(brief)
    if errs:
        return False, f"Schema errors: {'; '.join(errs)}"
    if brief.get("domain", "").lower() not in ("frontend", "ui", "web"):
        return False, f"Unexpected domain: {brief.get('domain')}"
    return True, "Valid frontend brief synthesized"


def test_t1_backend(client: StandaloneClient) -> Tuple[bool, str]:
    payload = {
        "task": "Develop a high-throughput REST API with JWT authentication, database connection pooling, and rate limiting",
        "constraints": ["runtime: Python 3.11+", "database: PostgreSQL", "latency: <50ms p95", "stateless auth"],
    }
    resp = client.post("/api/research", json_data=payload)
    if resp.status_code != 200:
        return False, f"Expected 200, got {resp.status_code}: {resp.text}"
    brief = resp.json()
    errs = validate_brief_schema(brief)
    if errs:
        return False, f"Schema errors: {'; '.join(errs)}"
    if brief.get("domain", "").lower() not in ("backend", "api", "microservice"):
        return False, f"Unexpected domain: {brief.get('domain')}"
    return True, "Valid backend brief synthesized"


def test_t1_data_pipeline(client: StandaloneClient) -> Tuple[bool, str]:
    payload = {
        "task": "Construct a streaming data pipeline ingesting 10,000 JSON events per second, validating schemas, deduplicating records, and batch-inserting into analytical storage",
        "constraints": ["throughput: 10k events/sec", "schema validation", "deduplication", "memory: <4GB"],
    }
    resp = client.post("/api/research", json_data=payload)
    if resp.status_code != 200:
        return False, f"Expected 200, got {resp.status_code}: {resp.text}"
    brief = resp.json()
    errs = validate_brief_schema(brief)
    if errs:
        return False, f"Schema errors: {'; '.join(errs)}"
    if brief.get("domain", "").lower() not in ("data_pipeline", "data", "pipeline", "etl"):
        return False, f"Unexpected domain: {brief.get('domain')}"
    return True, "Valid data pipeline brief synthesized"


def test_t1_devops(client: StandaloneClient) -> Tuple[bool, str]:
    payload = {
        "task": "Containerize and deploy a microservices application with health checking, graceful shutdown, automated TLS, and centralized telemetry",
        "constraints": ["platform: Docker/Kubernetes", "zero downtime", "observability: OpenTelemetry"],
    }
    resp = client.post("/api/research", json_data=payload)
    if resp.status_code != 200:
        return False, f"Expected 200, got {resp.status_code}: {resp.text}"
    brief = resp.json()
    errs = validate_brief_schema(brief)
    if errs:
        return False, f"Schema errors: {'; '.join(errs)}"
    if brief.get("domain", "").lower() not in ("devops_cloud", "devops", "cloud", "infra"):
        return False, f"Unexpected domain: {brief.get('domain')}"
    return True, "Valid devops brief synthesized"


# --- Tier 2 Tests ---

def test_t2_missing_task(client: StandaloneClient) -> Tuple[bool, str]:
    payload = {"constraints": ["target: cloud"]}
    resp = client.post("/api/research", json_data=payload)
    if resp.status_code not in (400, 422):
        return False, f"Expected 400 or 422, got {resp.status_code}"
    return True, f"Properly rejected with HTTP {resp.status_code}"


def test_t2_empty_task(client: StandaloneClient) -> Tuple[bool, str]:
    payload = {"task": "    ", "constraints": []}
    resp = client.post("/api/research", json_data=payload)
    if resp.status_code not in (400, 422):
        return False, f"Expected 400 or 422, got {resp.status_code}"
    return True, f"Properly rejected with HTTP {resp.status_code}"


def test_t2_invalid_task_type(client: StandaloneClient) -> Tuple[bool, str]:
    payload = {"task": 12345, "constraints": []}
    resp = client.post("/api/research", json_data=payload)
    if resp.status_code not in (400, 422):
        return False, f"Expected 400 or 422, got {resp.status_code}"
    return True, f"Properly rejected with HTTP {resp.status_code}"


def test_t2_invalid_constraints_type(client: StandaloneClient) -> Tuple[bool, str]:
    payload = {"task": "Valid task", "constraints": 99999}
    resp = client.post("/api/research", json_data=payload)
    if resp.status_code not in (400, 422):
        return False, f"Expected 400 or 422, got {resp.status_code}"
    return True, f"Properly rejected with HTTP {resp.status_code}"


def test_t2_empty_body(client: StandaloneClient) -> Tuple[bool, str]:
    resp = client.post_raw("/api/research", raw_body="")
    if resp.status_code not in (400, 422):
        return False, f"Expected 400 or 422, got {resp.status_code}"
    return True, f"Properly rejected with HTTP {resp.status_code}"


def test_t2_malformed_json(client: StandaloneClient) -> Tuple[bool, str]:
    resp = client.post_raw("/api/research", raw_body='{"task": "broken,')
    if resp.status_code not in (400, 422):
        return False, f"Expected 400 or 422, got {resp.status_code}"
    return True, f"Properly rejected with HTTP {resp.status_code}"


def test_t2_method_not_allowed(client: StandaloneClient) -> Tuple[bool, str]:
    resp = client.get("/api/research")
    if resp.status_code != 405:
        return False, f"Expected 405 Method Not Allowed, got {resp.status_code}"
    return True, "Properly returned HTTP 405"


def test_t2_not_found(client: StandaloneClient) -> Tuple[bool, str]:
    resp = client.get("/api/nonexistent_route_404")
    if resp.status_code != 404:
        return False, f"Expected 404 Not Found, got {resp.status_code}"
    return True, "Properly returned HTTP 404"


# --- Tier 3 Tests ---

def test_t3_high_concurrency(client: StandaloneClient) -> Tuple[bool, str]:
    payload = {
        "task": "Build a real-time WebSocket notification gateway sustaining 50,000 concurrent open connections",
        "constraints": ["concurrency: 50,000 active sockets", "memory bound: <1GB", "platform: Linux"],
    }
    resp = client.post("/api/research", json_data=payload)
    if resp.status_code != 200:
        return False, f"Expected 200, got {resp.status_code}: {resp.text}"
    brief = resp.json()
    errs = validate_brief_schema(brief)
    if errs:
        return False, f"Schema errors: {'; '.join(errs)}"
    return True, "High concurrency constraints handled"


def test_t3_ultra_low_latency(client: StandaloneClient) -> Tuple[bool, str]:
    payload = {
        "task": "Construct a financial tick data ingestion engine computing rolling features",
        "constraints": ["latency: <5ms p99", "zero-copy memory buffers", "in-memory processing"],
    }
    resp = client.post("/api/research", json_data=payload)
    if resp.status_code != 200:
        return False, f"Expected 200, got {resp.status_code}: {resp.text}"
    brief = resp.json()
    errs = validate_brief_schema(brief)
    if errs:
        return False, f"Schema errors: {'; '.join(errs)}"
    return True, "Ultra-low latency constraints handled"


def test_t3_offline_first(client: StandaloneClient) -> Tuple[bool, str]:
    payload = {
        "task": "Design a field inspection mobile web application with offline capture and reliable background sync",
        "constraints": ["offline-first architecture", "IndexedDB local storage", "ServiceWorker caching strategy"],
    }
    resp = client.post("/api/research", json_data=payload)
    if resp.status_code != 200:
        return False, f"Expected 200, got {resp.status_code}: {resp.text}"
    brief = resp.json()
    errs = validate_brief_schema(brief)
    if errs:
        return False, f"Schema errors: {'; '.join(errs)}"
    return True, "Offline-first PWA constraints handled"


# --- Tier 4 Tests ---

def test_t4_health(client: StandaloneClient) -> Tuple[bool, str]:
    resp = client.get("/api/health")
    if resp.status_code != 200:
        return False, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    if not isinstance(data, dict) or "status" not in data:
        return False, f"Missing 'status' in health JSON: {data}"
    return True, f"Health status: {data.get('status')}"


def test_t4_web_ui(client: StandaloneClient) -> Tuple[bool, str]:
    resp = client.get("/")
    if resp.status_code != 200:
        return False, f"Expected 200, got {resp.status_code}: {resp.text}"
    ct = resp.headers.get("content-type", "")
    if "text/html" not in ct.lower():
        return False, f"Content-Type not text/html: {ct}"
    if "The Researcher" not in resp.text:
        return False, "HTML missing branding 'The Researcher'"
    return True, "Web UI root delivered"


def test_t4_concurrency(client: StandaloneClient) -> Tuple[bool, str]:
    sample_requests = [
        {"task": "Frontend dashboard with real-time SVG charts", "constraints": ["browser: modern"]},
        {"task": "Backend microservice handling JWT authentication", "constraints": ["runtime: python"]},
        {"task": "Streaming event ingestion pipeline with deduplication", "constraints": ["scale: high"]},
        {"task": "Containerized microservice with health probes and TLS", "constraints": ["platform: docker"]},
        {"task": "Machine learning model serving endpoint with batching", "constraints": ["latency: <50ms"]},
    ]

    def _call(p):
        return client.post("/api/research", json_data=p)

    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(_call, p) for p in sample_requests]
        for f in as_completed(futures):
            res = f.result()
            if res.status_code != 200:
                return False, f"Concurrent call returned {res.status_code}: {res.text}"
            brief = res.json()
            errs = validate_brief_schema(brief)
            if errs:
                return False, f"Concurrent brief schema error: {'; '.join(errs)}"

    return True, "5 concurrent requests succeeded with 100% schema conformance"


def test_t4_uniqueness(client: StandaloneClient) -> Tuple[bool, str]:
    req_fe = {"task": "Accessible responsive web component hierarchy", "constraints": ["React"]}
    req_be = {"task": "Transactional payment processing ledger service", "constraints": ["PostgreSQL"]}

    r_fe = client.post("/api/research", json_data=req_fe)
    r_be = client.post("/api/research", json_data=req_be)

    if r_fe.status_code != 200 or r_be.status_code != 200:
        return False, "Synthesis requests failed"

    b_fe = r_fe.json()
    b_be = r_be.json()

    if b_fe.get("domain") == b_be.get("domain"):
        return False, f"Domains identical: {b_fe.get('domain')}"

    return True, "Dynamic outputs verified distinct across domains"


# ============================================================================
# Verification Battery Runner
# ============================================================================

ALL_TESTS: List[Tuple[str, str, str, Callable[[StandaloneClient], Tuple[bool, str]]]] = [
    # Tier 1
    ("Tier 1", "T1-FE-01", "Frontend Domain Synthesis", test_t1_frontend),
    ("Tier 1", "T1-BE-01", "Backend Domain Synthesis", test_t1_backend),
    ("Tier 1", "T1-DP-01", "Data Pipeline Domain Synthesis", test_t1_data_pipeline),
    ("Tier 1", "T1-DO-01", "DevOps & Cloud Domain Synthesis", test_t1_devops),
    # Tier 2
    ("Tier 2", "T2-ERR-01", "Missing Task Field (400/422)", test_t2_missing_task),
    ("Tier 2", "T2-ERR-02", "Empty/Whitespace Task (400/422)", test_t2_empty_task),
    ("Tier 2", "T2-ERR-03", "Invalid Task Field Type (422)", test_t2_invalid_task_type),
    ("Tier 2", "T2-ERR-04", "Invalid Constraints Type (422)", test_t2_invalid_constraints_type),
    ("Tier 2", "T2-ERR-05", "Empty Request Body (400/422)", test_t2_empty_body),
    ("Tier 2", "T2-ERR-06", "Malformed JSON Syntax (400/422)", test_t2_malformed_json),
    ("Tier 2", "T2-ERR-07", "Method Not Allowed (405)", test_t2_method_not_allowed),
    ("Tier 2", "T2-ERR-08", "Endpoint Not Found (404)", test_t2_not_found),
    # Tier 3
    ("Tier 3", "T3-CD-01", "High Concurrency (50k Sockets)", test_t3_high_concurrency),
    ("Tier 3", "T3-CD-02", "Ultra-Low Latency (<5ms p99)", test_t3_ultra_low_latency),
    ("Tier 3", "T3-CD-03", "Offline-First PWA (IndexedDB)", test_t3_offline_first),
    # Tier 4
    ("Tier 4", "T4-E2E-01", "Health Endpoint (/api/health)", test_t4_health),
    ("Tier 4", "T4-E2E-02", "Web UI Root Delivery (/)", test_t4_web_ui),
    ("Tier 4", "T4-E2E-03", "Concurrent Requests (5 parallel)", test_t4_concurrency),
    ("Tier 4", "T4-E2E-04", "Dynamic Brief Content Uniqueness", test_t4_uniqueness),
]


def run_verification(base_url: str, verbose: bool = False) -> List[TestResult]:
    client = StandaloneClient(base_url)
    results: List[TestResult] = []

    for tier, test_id, name, test_fn in ALL_TESTS:
        t0 = time.perf_counter()
        passed = False
        detail = ""
        try:
            passed, detail = test_fn(client)
        except Exception as ex:
            passed = False
            detail = f"Exception: {ex}"
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        results.append(TestResult(tier, test_id, name, passed, elapsed_ms, detail))

    return results


def print_table(results: List[TestResult], base_url: str, total_time_ms: float):
    print(f"\n{BOLD}{CYAN}========================================================================================{RESET}")
    print(f"{BOLD}{CYAN}           THE RESEARCHER - AUTOMATED VERIFICATION SUITE REPORT                        {RESET}")
    print(f"{BOLD}{CYAN}========================================================================================{RESET}")
    print(f"{DIM}Target Server: {base_url}{RESET}\n")

    header = f"{'Tier':<8} | {'Test ID':<10} | {'Test Name':<36} | {'Time (ms)':<10} | {'Status'}"
    print(f"{BOLD}{header}{RESET}")
    print("-" * 88)

    current_tier = ""
    for r in results:
        if r.tier != current_tier:
            if current_tier != "":
                print(f"{DIM}{'-' * 88}{RESET}")
            current_tier = r.tier

        status_str = f"{GREEN}[PASS]{RESET}" if r.passed else f"{RED}[FAIL]{RESET}"
        time_str = f"{r.duration_ms:6.1f}ms"
        print(f"{r.tier:<8} | {r.test_id:<10} | {r.name:<36} | {time_str:<10} | {status_str}")
        if not r.passed and r.detail:
            print(f"         {RED}--> Error: {r.detail}{RESET}")

    total_count = len(results)
    passed_count = sum(1 for r in results if r.passed)
    failed_count = total_count - passed_count
    pass_rate = (passed_count / total_count * 100.0) if total_count > 0 else 0.0

    print("=" * 88)
    summary_color = GREEN if failed_count == 0 else RED
    print(f"{BOLD}Summary:{RESET} Total: {total_count} | Passed: {GREEN}{passed_count}{RESET} | Failed: {RED}{failed_count}{RESET} | Pass Rate: {summary_color}{pass_rate:.1f}%{RESET} | Duration: {total_time_ms:.1f}ms")

    if failed_count == 0:
        print(f"\n{BOLD}{GREEN}>>> VERDICT: ALL TESTS PASSED. 100% SCHEMA CONFORMANCE VERIFIED. (EXIT 0) <<<{RESET}\n")
    else:
        print(f"\n{BOLD}{RED}>>> VERDICT: {failed_count} TEST(S) FAILED. VERIFICATION REJECTED. (EXIT 1) <<<{RESET}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="The Researcher Verification Runner")
    parser.add_argument("--url", type=str, default="", help="Target HTTP server URL (e.g. http://127.0.0.1:8000)")
    parser.add_argument("--port", type=int, default=8000, help="Server port if checking localhost")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON results")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print detailed diagnostic information")
    args = parser.parse_args()

    target_url = args.url
    server_obj = None
    server_thread = None

    if not target_url:
        default_candidate = f"http://127.0.0.1:{args.port}"
        if is_server_ready(default_candidate):
            target_url = default_candidate
        else:
            # Start ephemeral server
            ephemeral_port = find_free_port()
            target_url = f"http://127.0.0.1:{ephemeral_port}"
            if not args.json:
                print(f"{DIM}No server detected. Starting in-process server on {target_url}...{RESET}")
            try:
                server_obj, server_thread = start_ephemeral_server(ephemeral_port)
            except Exception as e:
                err_msg = f"Failed to launch in-process server: {e}"
                if args.json:
                    print(json.dumps({"status": "ERROR", "detail": err_msg, "exit_code": 1}))
                else:
                    print(f"{RED}{err_msg}{RESET}")
                return 1

            # Wait for server ready
            ready = False
            start_wait = time.time()
            while time.time() - start_wait < 5.0:
                if is_server_ready(target_url):
                    ready = True
                    break
                time.sleep(0.1)

            if not ready:
                err_msg = f"Timed out waiting for server to become ready on {target_url}"
                if args.json:
                    print(json.dumps({"status": "ERROR", "detail": err_msg, "exit_code": 1}))
                else:
                    print(f"{RED}{err_msg}{RESET}")
                return 1

    t_start = time.perf_counter()
    results = run_verification(target_url, verbose=args.verbose)
    total_time_ms = (time.perf_counter() - t_start) * 1000.0

    passed_count = sum(1 for r in results if r.passed)
    failed_count = len(results) - passed_count
    exit_code = 0 if failed_count == 0 else 1

    if args.json:
        json_output = {
            "status": "PASSED" if exit_code == 0 else "FAILED",
            "exit_code": exit_code,
            "total": len(results),
            "passed": passed_count,
            "failed": failed_count,
            "schema_conformance_rate": 1.0 if exit_code == 0 else (passed_count / len(results)),
            "duration_ms": round(total_time_ms, 2),
            "target_url": target_url,
            "results": [r.to_dict() for r in results],
        }
        print(json.dumps(json_output, indent=2))
    else:
        print_table(results, target_url, total_time_ms)

    # Clean shutdown of ephemeral server if started
    if server_obj is not None and hasattr(server_obj, "shutdown"):
        try:
            server_obj.shutdown()
            server_obj.server_close()
        except Exception:
            pass

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
