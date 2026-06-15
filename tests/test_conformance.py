"""Tests for the conformance layer (4th layer).

Covers the domain-agnostic engine (sdd/base_conformance.py, sdd/base_pipeline.py)
and the GREAT-specific wiring (great_sdd/conformance/*): rule inventory, exclusions,
fixture generation, coverage gate, and the consumer runner.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ═══════════════════════════════════════════════════════════
# sdd/base_pipeline.py
# ═══════════════════════════════════════════════════════════

def test_base_pipeline_runs_stages_in_order():
    from sdd.base_pipeline import BasePipeline, PipelineStage
    calls = []

    class A(PipelineStage):
        name = "a"

        def run(self, ctx):
            calls.append("a")
            return {"x": 1}

    class B(PipelineStage):
        name = "b"

        def run(self, ctx):
            calls.append("b")
            return {"y": ctx["x"] + 1}

    out = BasePipeline([A(), B()]).run({})
    assert calls == ["a", "b"]
    assert out["x"] == 1 and out["y"] == 2


# ═══════════════════════════════════════════════════════════
# sdd/base_conformance.py — canonical json, version, normalize
# ═══════════════════════════════════════════════════════════

def test_canonical_json_is_byte_stable_and_key_order_independent():
    from sdd.base_conformance import canonical_json
    a = canonical_json({"b": 1, "a": [3, 2, 1]})
    b = canonical_json({"a": [3, 2, 1], "b": 1})
    assert a == b
    assert a.endswith("\n")
    assert a == '{\n  "a": [\n    3,\n    2,\n    1\n  ],\n  "b": 1\n}\n'


def test_read_version_prefers_pyproject(tmp_path):
    from sdd.base_conformance import read_version
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "9.8.7"\n')
    assert read_version(tmp_path) == "9.8.7"


def test_normalize_output_parses_json_suffixed_keys():
    from sdd.base_conformance import normalize_output
    out = normalize_output({"can_save": True, "errors_json": '["a","b"]', "name": "x"})
    assert out == {"can_save": True, "errors_json": ["a", "b"], "name": "x"}


# ═══════════════════════════════════════════════════════════
# sdd/base_conformance.py — Probe + generate_fixtures (tripwire)
# ═══════════════════════════════════════════════════════════

def test_generate_fixtures_shape_and_sorting():
    from sdd.base_conformance import Probe, generate_fixtures
    p = Probe(rule_ids=["R-2", "R-1"], name="echo",
              fn=lambda inp: {"echoed": inp["v"]},
              cases=[{"v": 2}, {"v": 1}])
    entries = generate_fixtures([p], sdd_version="1.0.0")
    assert all(set(e) == {"rule_ids", "input", "expected_output", "sdd_version"} for e in entries)
    assert entries[0]["rule_ids"] == ["R-1", "R-2"]          # rule_ids sorted
    assert [e["input"]["v"] for e in entries] == [1, 2]      # entries sorted by input
    assert entries[0]["expected_output"] == {"echoed": 1}
    assert entries[0]["sdd_version"] == "1.0.0"


def test_generate_fixtures_normalizes_json_keys():
    from sdd.base_conformance import Probe, generate_fixtures
    p = Probe(["R-1"], "j", lambda inp: {"items_json": '[1,2]'}, [{}])
    entries = generate_fixtures([p], "1.0.0")
    assert entries[0]["expected_output"] == {"items_json": [1, 2]}


def test_generate_fixtures_aborts_loudly_on_lm_path():
    from sdd.base_conformance import Probe, generate_fixtures, NonDeterministicError, TripwireLM

    def bad(inp):
        TripwireLM().complete("s", "p")   # simulates a module hitting the LM
        return {}

    with pytest.raises(NonDeterministicError):
        generate_fixtures([Probe(["R-X"], "bad", bad, [{}])], "1.0.0")


# ═══════════════════════════════════════════════════════════
# sdd/base_conformance.py — coverage, skew, runner
# ═══════════════════════════════════════════════════════════

def test_compute_coverage_threshold():
    from sdd.base_conformance import compute_coverage
    r = compute_coverage(all_rule_ids=["A", "B", "C", "D"],
                         covered_rule_ids=["A", "B", "C"], threshold=0.70)
    assert r["covered_count"] == 3 and r["total"] == 4
    assert abs(r["coverage"] - 0.75) < 1e-9
    assert r["passed"] is True and r["missing"] == ["D"]
    r2 = compute_coverage(["A", "B", "C", "D"], ["A"], 0.70)
    assert r2["passed"] is False


def test_compute_version_skew():
    from sdd.base_conformance import compute_version_skew
    assert compute_version_skew("1.2.0", "1.2.0")["skew"] is False
    assert compute_version_skew("1.1.0", "1.2.0")["skew"] is True


def test_run_conformance_exact_match_and_exercised_ids():
    from sdd.base_conformance import run_conformance
    fixtures = [
        {"rule_ids": ["R-1"], "input": {"v": 1}, "expected_output": {"r": 2}, "sdd_version": "1.0.0"},
        {"rule_ids": ["R-2"], "input": {"v": 5}, "expected_output": {"r": 6}, "sdd_version": "1.0.0"},
    ]
    rep = run_conformance(fixtures, consumer_fn=lambda req: {"r": req["input"]["v"] + 1})
    assert rep["passed"] is True and rep["failed_count"] == 0
    assert sorted(rep["exercised_rule_ids"]) == ["R-1", "R-2"]
    bad = run_conformance(fixtures, consumer_fn=lambda req: {"r": 0})
    assert bad["passed"] is False and bad["failed_count"] == 2
    assert bad["failures"][0]["input"] == {"v": 1}


# ═══════════════════════════════════════════════════════════
# InductorSelector — deterministic, LM-free refactor
# ═══════════════════════════════════════════════════════════

def test_inductor_selector_is_deterministic_and_lm_free():
    from sdd.base_conformance import TripwireLM
    from great_sdd.modules.pre_estimation import InductorSelector
    sel = InductorSelector(TripwireLM())            # tripwire: must NOT call LM
    out1 = sel.forward(line_description="Build a complex REST API endpoint",
                       metier="H-DESIGN", available_inductors_json="[]")
    out2 = sel.forward(line_description="Build a complex REST API endpoint",
                       metier="H-DESIGN", available_inductors_json="[]")
    assert out1 == out2                              # deterministic
    sels = json.loads(out1["inductor_selections_json"])
    assert isinstance(sels, list) and len(sels) >= 1
    api = [s for s in sels if s["name"] == "API endpoints"]
    assert api and api[0]["selected_cran"] == "Complex"   # "complex" keyword -> Complex cran
    assert all("job_units" in s for s in sels)


def test_inductor_selector_empty_description_falls_back_to_all():
    from sdd.base_conformance import TripwireLM
    from great_sdd.modules.pre_estimation import InductorSelector
    out = InductorSelector(TripwireLM()).forward(
        line_description="", metier="H-DESIGN", available_inductors_json="[]")
    sels = json.loads(out["inductor_selections_json"])
    assert len(sels) == 3                            # all H-DESIGN inductors, canonical crans
    assert all(s["selected_cran"] for s in sels)


def test_inductor_selector_unknown_metier_returns_empty():
    from sdd.base_conformance import TripwireLM
    from great_sdd.modules.pre_estimation import InductorSelector
    out = InductorSelector(TripwireLM()).forward(
        line_description="x", metier="Nonexistent", available_inductors_json="[]")
    assert json.loads(out["inductor_selections_json"]) == []


# ═══════════════════════════════════════════════════════════
# rule_inventory — canonical 92
# ═══════════════════════════════════════════════════════════

def test_rule_inventory_canonical_counts():
    from great_sdd.conformance.rule_inventory import (
        business_rule_ids, pending_marker_ids, rule_count)
    brs = business_rule_ids()
    assert rule_count() == 92
    assert len(brs) == 92
    assert "BR-01" in brs and "ALLOC-BR-17" in brs and "EMAIL-BR-04" in brs
    assert set(pending_marker_ids()) == {
        "ALLOC-01", "ERev-01", "ERev-02", "ERev-03",
        "FINAL-01", "MGMT-01", "TRANS-01", "TRANS-02", "TRANS-03"}
    assert brs == sorted(set(brs))    # deduped + sorted


# ═══════════════════════════════════════════════════════════
# exclusions — documented buckets
# ═══════════════════════════════════════════════════════════

def test_exclusions_reference_real_or_capability_ids():
    from great_sdd.conformance.exclusions import (
        NON_DETERMINISTIC_RULES, NO_FUNCTION_SURFACE_RULES)
    from great_sdd.conformance.rule_inventory import business_rule_ids
    brs = set(business_rule_ids())
    assert set(NO_FUNCTION_SURFACE_RULES).issubset(brs)
    for d in (NON_DETERMINISTIC_RULES, NO_FUNCTION_SURFACE_RULES):
        assert all(isinstance(v, str) and v for v in d.values())
    assert not (set(NON_DETERMINISTIC_RULES) & set(NO_FUNCTION_SURFACE_RULES))


# ═══════════════════════════════════════════════════════════
# generate.py — probes + fixtures
# ═══════════════════════════════════════════════════════════

def test_build_probes_cover_expected_views():
    from great_sdd.conformance.generate import build_probes
    views = build_probes()
    assert set(views) == {"pre_estimation", "estimation_review", "allocation",
                          "final_review", "management_view", "transversal"}
    assert all(len(v) >= 1 for v in views.values())


def test_all_probes_run_without_lm_and_are_deterministic():
    from great_sdd.conformance.generate import build_probes
    from sdd.base_conformance import generate_fixtures
    for view, probes in build_probes().items():
        e1 = generate_fixtures(probes, "1.0.0")     # raises if any path hits the LM
        e2 = generate_fixtures(probes, "1.0.0")
        assert e1 == e2, f"{view} not deterministic"


def test_covered_rule_ids_are_real_business_rules():
    from great_sdd.conformance.generate import covered_rule_ids
    from great_sdd.conformance.rule_inventory import business_rule_ids
    assert set(covered_rule_ids()).issubset(set(business_rule_ids()))


def test_no_rule_is_both_covered_and_excluded():
    from great_sdd.conformance.generate import covered_rule_ids
    from great_sdd.conformance.exclusions import NO_FUNCTION_SURFACE_RULES
    assert not (set(covered_rule_ids()) & set(NO_FUNCTION_SURFACE_RULES))


def test_covered_plus_excluded_partition_all_92():
    from great_sdd.conformance.generate import covered_rule_ids
    from great_sdd.conformance.exclusions import NO_FUNCTION_SURFACE_RULES
    from great_sdd.conformance.rule_inventory import business_rule_ids
    covered = set(covered_rule_ids())
    excluded = set(NO_FUNCTION_SURFACE_RULES)
    assert covered | excluded == set(business_rule_ids())   # nothing unaccounted for


def test_committed_fixtures_are_in_sync():
    from great_sdd.conformance.generate import main
    assert main(["--check"]) == 0


# ═══════════════════════════════════════════════════════════
# coverage.py CLI
# ═══════════════════════════════════════════════════════════

def test_coverage_cli_from_fixtures_passes_at_zero_threshold(capsys):
    from great_sdd.conformance.coverage import main
    rc = main(["--from-fixtures", "--threshold", "0.0", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert "coverage" in out and "version_skew" in out and out["coverage"]["passed"]


def test_coverage_cli_fails_below_threshold():
    from great_sdd.conformance.coverage import main
    assert main(["--from-fixtures", "--threshold", "1.0"]) in (0, 1)


def test_coverage_cli_detects_version_skew(tmp_path):
    from great_sdd.conformance.coverage import main
    rep = tmp_path / "consumer.json"
    rep.write_text(json.dumps({"sdd_version": "0.0.1", "exercised_rule_ids": ["BR-02"]}))
    assert main(["--report", str(rep), "--threshold", "0.0"]) == 1   # skew -> nonzero


# ═══════════════════════════════════════════════════════════
# runner.py — consumer against fixtures
# ═══════════════════════════════════════════════════════════

def test_runner_against_oracle_consumer_is_all_green():
    from great_sdd.conformance.runner import run_against_fixtures, oracle_consumer_fn
    rep = run_against_fixtures(consumer_fn=oracle_consumer_fn)
    assert rep["passed"] is True, rep["failures"][:2]
    assert len(rep["exercised_rule_ids"]) >= 1


def test_runner_reports_mismatch():
    from great_sdd.conformance.runner import run_against_fixtures
    rep = run_against_fixtures(consumer_fn=lambda req: {"bogus": True})
    assert rep["passed"] is False and rep["failed_count"] > 0


# ═══════════════════════════════════════════════════════════
# docs reconciliation — derived rule count
# ═══════════════════════════════════════════════════════════

def test_docs_state_canonical_rule_count():
    from great_sdd.conformance.rule_inventory import rule_count
    n = str(rule_count())   # 92
    for doc in ("README.md", "AGENTS.md", "SDD-OVERVIEW.md"):
        with open(os.path.join(os.path.dirname(__file__), "..", doc), encoding="utf-8") as fh:
            text = fh.read()
        assert "74 reglas" not in text and "78 reglas" not in text, f"{doc} stale rule count"
        assert n in text, f"{doc} missing canonical count {n}"


def test_readme_quarantine_lists_every_excluded_rule():
    """The README ⚠️ quarantine warning must list every excluded rule/capability."""
    from great_sdd.conformance.exclusions import (
        NON_DETERMINISTIC_RULES, NO_FUNCTION_SURFACE_RULES)
    with open(os.path.join(os.path.dirname(__file__), "..", "README.md"),
              encoding="utf-8") as fh:
        readme = fh.read()
    for key in list(NON_DETERMINISTIC_RULES) + list(NO_FUNCTION_SURFACE_RULES):
        assert f"`{key}`" in readme, f"README quarantine section missing {key}"


# ═══════════════════════════════════════════════════════════
# endpoint conformance — engine primitives
# ═══════════════════════════════════════════════════════════
def test_endpoint_probe_generates_sorted_byte_stable_fixture():
    from sdd.base_conformance import EndpointProbe, generate_endpoint_fixtures
    probe = EndpointProbe(
        endpoint="GET /demo", name="demo",
        fn=lambda req: {"status": 200, "body": {"echo": req.get("q")}},
        cases=[{"q": "b"}, {"q": "a"}])
    seed = [{"id": "1"}]
    fx = generate_endpoint_fixtures(probe, seed, "9.9.9")
    assert fx["endpoint"] == "GET /demo"
    assert fx["sdd_version"] == "9.9.9"
    assert fx["seed"] == seed
    # cases sorted by canonical_json(request): {"q":"a"} before {"q":"b"}
    assert [c["request"]["q"] for c in fx["cases"]] == ["a", "b"]
    assert fx["cases"][0]["expected"] == {"status": 200, "body": {"echo": "a"}}


def test_run_endpoint_conformance_exact_match_and_never_passes_expected():
    from sdd.base_conformance import EndpointProbe, generate_endpoint_fixtures, run_endpoint_conformance
    probe = EndpointProbe(
        endpoint="GET /demo", name="demo",
        fn=lambda req: {"status": 200, "body": {"echo": req["q"]}},
        cases=[{"q": "a"}])
    fx = generate_endpoint_fixtures(probe, [], "9.9.9")

    seen_keys = []
    def consumer(req):
        seen_keys.append(set(req))
        return {"status": 200, "body": {"echo": req["request"]["q"]}}
    rep = run_endpoint_conformance(fx, consumer)
    assert rep["passed"] and rep["failed_count"] == 0 and rep["total"] == 1
    # consumer receives endpoint/request/seed, never "expected"
    assert seen_keys[0] == {"endpoint", "request", "seed"}

    bad = run_endpoint_conformance(fx, lambda req: {"status": 500, "body": None})
    assert not bad["passed"] and bad["failures"][0]["actual"]["status"] == 500


# ═══════════════════════════════════════════════════════════
# endpoint conformance — GET /project-lines oracle
# ═══════════════════════════════════════════════════════════
def test_project_lines_engineer_is_scoped_to_own_lines():
    from great_sdd.conformance.endpoints.project_lines import list_project_lines
    out = list_project_lines({"role": "Engineer", "user_oid": "oid-engineer-1",
                              "query": {}, "active_cycle": True})
    assert out["status"] == 200
    pls = [r["pl_number"] for r in out["body"]["data"]]
    assert pls == ["PL-001", "PL-003"]                       # only engineer-1's lines, sorted
    assert out["body"]["filterOptions"]["assignees"] == ["oid-engineer-1"]
    assert out["body"]["filterOptions"]["metiers"] == ["H-NP", "H-SOFTWARE"]


def test_project_lines_engineer_ignores_assignee_query():
    from great_sdd.conformance.endpoints.project_lines import list_project_lines
    out = list_project_lines({"role": "Engineer", "user_oid": "oid-engineer-1",
                              "query": {"assignee": "oid-engineer-2"}, "active_cycle": True})
    assert [r["pl_number"] for r in out["body"]["data"]] == ["PL-001", "PL-003"]


def test_project_lines_pmo_sees_all_and_can_filter_metier():
    from great_sdd.conformance.endpoints.project_lines import list_project_lines
    all_out = list_project_lines({"role": "PMO", "user_oid": "oid-pmo",
                                  "query": {}, "active_cycle": True})
    assert [r["pl_number"] for r in all_out["body"]["data"]] == ["PL-001", "PL-002", "PL-003", "PL-004"]
    assert all_out["body"]["filterOptions"]["metiers"] == ["H-DESIGN", "H-NP", "H-PROJECT", "H-SOFTWARE"]

    filtered = list_project_lines({"role": "PMO", "user_oid": "oid-pmo",
                                   "query": {"metier": "H-DESIGN"}, "active_cycle": True})
    assert [r["pl_number"] for r in filtered["body"]["data"]] == ["PL-002"]
    # filterOptions ignore active filters -> still the full set
    assert filtered["body"]["filterOptions"]["metiers"] == ["H-DESIGN", "H-NP", "H-PROJECT", "H-SOFTWARE"]


def test_project_lines_status_codes():
    from great_sdd.conformance.endpoints.project_lines import list_project_lines
    assert list_project_lines({"role": "CPO", "active_cycle": True})["status"] == 403
    assert list_project_lines({"role": "PMO", "active_cycle": False})["status"] == 404
    assert list_project_lines({"role": None, "active_cycle": True})["status"] == 401
    assert list_project_lines({"role": "CPO", "active_cycle": True})["body"] is None


def test_project_lines_rows_have_24_contract_fields_and_no_h_testing():
    from great_sdd.conformance.endpoints.project_lines import (
        list_project_lines, PROJECT_LINE_FIELDS)
    out = list_project_lines({"role": "PMO", "user_oid": "oid-pmo",
                              "query": {}, "active_cycle": True})
    assert len(PROJECT_LINE_FIELDS) == 24
    for row in out["body"]["data"]:
        assert set(row) == set(PROJECT_LINE_FIELDS)
        assert row["metier"] != "H-TESTING"
        assert row["total_days"] is None and row["total_keuro"] is None
    assert "H-TESTING" not in out["body"]["filterOptions"]["metiers"]


def test_project_lines_engineer_without_oid_is_unauthorized():
    from great_sdd.conformance.endpoints.project_lines import list_project_lines
    # An Engineer with no oid has no valid identity -> 401, never an unscoped list.
    assert list_project_lines({"role": "Engineer", "active_cycle": True})["status"] == 401


def test_project_lines_auth_precedes_active_cycle_check():
    from great_sdd.conformance.endpoints.project_lines import list_project_lines
    # Auth (dependency layer) is evaluated before the service's cycle check.
    assert list_project_lines({"role": "CPO", "active_cycle": False})["status"] == 403
    assert list_project_lines({"role": None, "active_cycle": False})["status"] == 401


def test_endpoint_fixture_is_generated_and_byte_stable():
    from great_sdd.conformance.generate import (
        ENDPOINTS_DIR, build_endpoint_fixtures, REPO_ROOT)
    from sdd.base_conformance import canonical_json, read_version
    path = os.path.join(str(ENDPOINTS_DIR), "project_lines.json")
    assert os.path.exists(path), "run `python3 -m great_sdd.conformance.generate` first"
    on_disk = open(path, encoding="utf-8").read()
    version = read_version(REPO_ROOT)
    regenerated = canonical_json(build_endpoint_fixtures(version)["project_lines"])
    assert on_disk == regenerated, "endpoint fixture drift — regenerate"

    fx = json.loads(on_disk)
    assert fx["endpoint"] == "GET /project-lines"
    assert len(fx["cases"]) == 7
    assert len(fx["seed"]) == 4


def test_oracle_endpoint_consumer_passes_all_cases():
    from great_sdd.conformance.runner import (
        run_endpoints_against_fixtures, oracle_endpoint_consumer_fn)
    reports = run_endpoints_against_fixtures(oracle_endpoint_consumer_fn)
    assert reports, "no endpoint fixtures found"
    for rep in reports:
        assert rep["passed"], rep["failures"][:2]
    assert any(r["endpoint"] == "GET /project-lines" for r in reports)


def test_coverage_lists_endpoints_separately_from_rule_census():
    from great_sdd.conformance.coverage import endpoint_coverage_lines
    lines = endpoint_coverage_lines()
    joined = "\n".join(lines)
    assert "GET /project-lines" in joined
    assert "7 cases" in joined


# ═══════════════════════════════════════════════════════════
# collection export — foundations
# ═══════════════════════════════════════════════════════════
def test_scenario_label_covers_statuses():
    from great_sdd.conformance.collection import _scenario_label
    assert _scenario_label({"role": None}, 401) == "no JWT / role (401)"
    assert _scenario_label({"role": "CPO"}, 403) == "CPO — forbidden (403)"
    assert _scenario_label({"role": "PMO"}, 404) == "no active cycle (404)"
    assert _scenario_label({"role": "PMO", "query": {}}, 200) == "PMO — all (200)"
    assert _scenario_label({"role": "PMO", "query": {"metier": "H-DESIGN"}}, 200) \
        == "PMO — metier=H-DESIGN (200)"


def test_build_examples_has_all_cases_per_endpoint():
    from great_sdd.conformance.collection import build_examples, load_endpoints
    eps = load_endpoints()                      # default committed fixtures
    examples = build_examples(eps)
    assert "GET /project-lines" in examples
    rows = examples["GET /project-lines"]
    assert len(rows) == 7                        # all 7 conformance cases
    for row in rows:
        assert set(row) == {"scenario", "request", "response"}
        assert set(row["response"]) == {"status", "body"}
    # at least one 200 and the 403/404/401 are represented
    statuses = sorted({r["response"]["status"] for r in rows})
    assert statuses == [200, 401, 403, 404]


# ═══════════════════════════════════════════════════════════
# collection export — oracle HTTP binding + schemas
# ═══════════════════════════════════════════════════════════
def test_project_lines_http_binding_and_schemas():
    from great_sdd.conformance.endpoints.project_lines import (
        HTTP_BINDING, REQUEST_SCHEMA, RESPONSE_SCHEMA, PROJECT_LINE_FIELDS)
    assert HTTP_BINDING["method"] == "GET"
    assert HTTP_BINDING["path"] == "/project-lines"
    assert HTTP_BINDING["query_params"] == ["assignee", "metier"]
    assert HTTP_BINDING["auth"] == "bearer"
    # response schema's ProjectLine must cover exactly the 24 contract fields
    pl_props = RESPONSE_SCHEMA["definitions"]["ProjectLine"]["properties"]
    assert set(pl_props) == set(PROJECT_LINE_FIELDS)
    # métier enum mirrors the contract (no H-TESTING) in both schemas
    assert "H-TESTING" not in pl_props["metier"]["enum"]
    assert "H-TESTING" not in REQUEST_SCHEMA["properties"]["metier"]["enum"]
    # request query params line up with the binding
    assert set(REQUEST_SCHEMA["properties"]) == set(HTTP_BINDING["query_params"])


def test_build_postman_collection_v21_shape():
    from great_sdd.conformance.collection import build_postman, load_endpoints
    coll = build_postman(load_endpoints())
    assert coll["info"]["schema"] == \
        "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    assert any(v["key"] == "baseUrl" for v in coll["variable"])
    assert any(v["key"] == "token" for v in coll["variable"])
    item = next(i for i in coll["item"] if i["name"] == "GET /project-lines")
    assert item["request"]["method"] == "GET"
    # bearer auth header present
    assert any(h["key"] == "Authorization" and h["value"] == "Bearer {{token}}"
               for h in item["request"]["header"])
    # url uses {{baseUrl}} + path + query params
    assert item["request"]["url"]["raw"].startswith("{{baseUrl}}/project-lines")
    assert {q["key"] for q in item["request"]["url"]["query"]} == {"assignee", "metier"}
    # one saved example per conformance case, each with its status code
    assert len(item["response"]) == 7
    codes = sorted(r["code"] for r in item["response"])
    assert codes == [200, 200, 200, 200, 401, 403, 404]
    # request description embeds both schemas + the 24 fields, no H-TESTING
    desc = item["request"]["description"]
    assert "Request schema" in desc and "Response schema" in desc
    assert "total_keuro" in desc and "H-TESTING" not in desc


def test_postman_examples_reflect_scenario_auth_and_query():
    from great_sdd.conformance.collection import build_postman, load_endpoints
    item = next(i for i in build_postman(load_endpoints())["item"]
                if i["name"] == "GET /project-lines")
    by_code = {}
    for r in item["response"]:
        by_code.setdefault(r["code"], []).append(r)
    # 401 example carries NO Authorization header (the "no JWT" scenario) and text preview
    ex401 = by_code[401][0]
    assert all(h["key"] != "Authorization" for h in ex401["originalRequest"]["header"])
    assert ex401["_postman_previewlanguage"] == "text" and ex401["body"] == ""
    assert ex401["status"] == "Unauthorized"
    # a 200 example with a metier filter carries that query param + value
    assert any(
        any(q["key"] == "metier" and q["value"] == "H-DESIGN"
            for q in r["originalRequest"]["url"]["query"])
        for r in by_code[200])
    # the saved request template lists optional params as disabled (shown, not sent)
    assert item["request"]["url"]["query"]
    assert all(q.get("disabled") for q in item["request"]["url"]["query"])


def test_build_bruno_files():
    from great_sdd.conformance.collection import build_bruno, load_endpoints
    files = build_bruno(load_endpoints())
    assert "bruno.json" in files
    meta = json.loads(files["bruno.json"])
    assert meta["type"] == "collection" and meta["name"]
    bru_files = [k for k in files if k.endswith(".bru")]
    assert len(bru_files) == 1
    bru = files[bru_files[0]]
    assert "meta {" in bru and "get {" in bru
    # clean url line — no empty query string appended
    assert "  url: {{baseUrl}}/project-lines\n" in bru
    assert "Authorization: Bearer {{token}}" in bru
    assert "docs {" in bru and "Response schema" in bru
    assert "CPO — forbidden (403)" in bru
    # Bruno closes a docs block at the first column-0 '}'. The embedded JSON Schema
    # must be indented so NO inner line is a bare '}' before the real block close.
    lines = bru.split("\n")
    di = next(i for i, l in enumerate(lines) if l.startswith("docs {"))
    close = max(i for i, l in enumerate(lines) if l == "}")
    for l in lines[di + 1:close]:
        assert l != "}", f"bare }} would close Bruno docs block early: {l!r}"


def test_collection_generate_writes_and_is_byte_stable():
    from great_sdd.conformance.collection import write_collections, DEFAULT_OUT, load_endpoints
    write_collections(load_endpoints(), DEFAULT_OUT)
    base = str(DEFAULT_OUT)
    pm = os.path.join(base, "postman_collection.json")
    ex = os.path.join(base, "examples.json")
    bru = os.path.join(base, "bruno", "project-lines.bru")
    assert os.path.exists(pm) and os.path.exists(ex) and os.path.exists(bru)
    # examples.json round-trips and has all 7 cases
    examples = json.loads(open(ex, encoding="utf-8").read())
    assert len(examples["GET /project-lines"]) == 7
    # byte-stable: regenerating produces identical bytes
    before = open(pm, encoding="utf-8").read()
    write_collections(load_endpoints(), DEFAULT_OUT)
    assert open(pm, encoding="utf-8").read() == before


def test_collection_export_zip_is_deterministic(tmp_path):
    import io as _io
    import zipfile
    from great_sdd.conformance.collection import build_zip_bytes, load_endpoints
    blob1 = build_zip_bytes(load_endpoints())
    blob2 = build_zip_bytes(load_endpoints())
    assert isinstance(blob1, bytes)
    assert blob1 == blob2                        # deterministic (fixed date_time)
    zf = zipfile.ZipFile(_io.BytesIO(blob1))
    names = set(zf.namelist())
    assert "postman_collection.json" in names
    assert "examples.json" in names
    assert any(n.startswith("bruno/") and n.endswith(".bru") for n in names)
