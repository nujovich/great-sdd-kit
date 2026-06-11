"""Export Bruno + Postman collections from conformance endpoint fixtures.

Reads each fixtures/endpoints/*.json plus the per-endpoint HTTP_BINDING and
REQUEST_SCHEMA/RESPONSE_SCHEMA declared on its oracle module, and emits:
  - postman_collection.json (Postman Collection v2.1)
  - bruno/ (native .bru files + bruno.json)
  - examples.json (every conformance case per endpoint, human-readable)

The N logical conformance cases (PMO->200, CPO->403, ...) collapse into ONE HTTP
request per endpoint with one saved example per case. Deterministic, byte-stable,
stdlib-only. Does NOT enter the business-rule census.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import zipfile
from pathlib import Path

from sdd.base_conformance import canonical_json
from great_sdd.conformance.generate import ENDPOINTS_DIR
from great_sdd.conformance.endpoints import project_lines as _project_lines_ep

DEFAULT_OUT = ENDPOINTS_DIR / "collections"

# endpoint name -> oracle module exposing HTTP_BINDING / REQUEST_SCHEMA / RESPONSE_SCHEMA
_ENDPOINT_MODULES = {
    "GET /project-lines": _project_lines_ep,
}


def _load_endpoint_fixtures(fixtures_dir: Path) -> list:
    """Parsed endpoint fixtures from <fixtures_dir>/*.json (non-recursive)."""
    return [json.loads(fp.read_text())
            for fp in sorted(Path(fixtures_dir).glob("*.json"))]


def load_endpoints(fixtures_dir: Path = ENDPOINTS_DIR) -> list:
    """List of {name, fixture, module} for each endpoint fixture found."""
    endpoints = []
    for fx in _load_endpoint_fixtures(fixtures_dir):
        name = fx["endpoint"]
        if name not in _ENDPOINT_MODULES:
            raise ValueError(
                f"No oracle module registered for endpoint {name!r}; "
                f"add it to _ENDPOINT_MODULES in collection.py.")
        endpoints.append({"name": name, "fixture": fx,
                          "module": _ENDPOINT_MODULES[name]})
    return endpoints


def _scenario_label(case: dict, status: int) -> str:
    """Human-readable label for a conformance case, by status + request."""
    role = case.get("role")
    if status == 401:
        return "no JWT / role (401)"
    if status == 403:
        return f"{role} — forbidden (403)"
    if status == 404:
        return "no active cycle (404)"
    query = case.get("query") or {}
    bits = [f"{k}={query[k]}" for k in ("assignee", "metier") if query.get(k)]
    suffix = ", ".join(bits) if bits else "all"
    return f"{role} — {suffix} (200)"


def build_examples(endpoints: list) -> dict:
    """endpoint name -> [{scenario, request, response:{status, body}}] for every case."""
    out = {}
    for ep in endpoints:
        rows = []
        for case in ep["fixture"]["cases"]:
            status = case["expected"]["status"]
            rows.append({
                "scenario": _scenario_label(case["request"], status),
                "request": case["request"],
                "response": {"status": status, "body": case["expected"]["body"]},
            })
        out[ep["name"]] = rows
    return out


def _markdown_docs(binding: dict, request_schema: dict, response_schema: dict) -> str:
    """Markdown for a request description: both JSON Schemas + auth note."""
    return (
        f"`{binding['method']} {{{{baseUrl}}}}{binding['path']}`\n\n"
        f"Auth: Bearer `{{{{token}}}}`.\n\n"
        "## Request schema\n\n```json\n"
        + canonical_json(request_schema).rstrip()
        + "\n```\n\n## Response schema\n\n```json\n"
        + canonical_json(response_schema).rstrip()
        + "\n```\n"
    )


def _pm_url(binding: dict, query: dict = None) -> dict:
    """Postman url object: {{baseUrl}} + path segments + query params."""
    query = query or {}
    qitems = [{"key": k, "value": str(query.get(k, ""))}
              for k in binding.get("query_params", [])]
    raw = "{{baseUrl}}" + binding["path"]
    if qitems:
        raw += "?" + "&".join(f"{q['key']}={q['value']}" for q in qitems)
    return {
        "raw": raw,
        "host": ["{{baseUrl}}"],
        "path": [seg for seg in binding["path"].split("/") if seg],
        "query": qitems,
    }


def _pm_headers(binding: dict) -> list:
    headers = []
    if binding.get("auth") == "bearer":
        headers.append({"key": "Authorization", "value": "Bearer {{token}}"})
    return headers


def build_postman(endpoints: list) -> dict:
    """Postman Collection v2.1: one item per endpoint, one saved example per case."""
    items = []
    for ep in endpoints:
        binding = ep["module"].HTTP_BINDING
        desc = _markdown_docs(binding, ep["module"].REQUEST_SCHEMA,
                              ep["module"].RESPONSE_SCHEMA)
        headers = _pm_headers(binding)
        responses = []
        for case in ep["fixture"]["cases"]:
            status = case["expected"]["status"]
            body = case["expected"]["body"]
            responses.append({
                "name": _scenario_label(case["request"], status),
                "originalRequest": {
                    "method": binding["method"], "header": headers,
                    "url": _pm_url(binding, (case["request"].get("query") or {})),
                },
                "code": status,
                "_postman_previewlanguage": "json",
                "header": [{"key": "Content-Type", "value": "application/json"}],
                "body": canonical_json(body).rstrip() if body is not None else "",
            })
        items.append({
            "name": ep["name"],
            "request": {"method": binding["method"], "header": headers,
                        "url": _pm_url(binding), "description": desc},
            "response": responses,
        })
    return {
        "info": {
            "name": "GREAT API — conformance collection",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            "description": "Generated from great_sdd conformance endpoint fixtures. "
                           "Set {{baseUrl}} and {{token}} before sending.",
        },
        "variable": [
            {"key": "baseUrl", "value": "/api/v1"},
            {"key": "token", "value": "<JWT>"},
        ],
        "item": items,
    }
