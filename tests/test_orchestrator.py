"""Unit tests for orchestrator/merge.py."""
import copy
import json
from pathlib import Path
import pytest

from orchestrator.merge import (
    MergeEngineError,
    load_fixtures_from_dir,
    reconcile_verdict,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def standard_fixtures():
    """Load the standard Phase 3 fixtures."""
    vd, vl, ui, fv, rr = load_fixtures_from_dir(FIXTURES_DIR)
    return {
        "version_diff": vd,
        "vuln_lookup": vl,
        "usage_impact": ui,
        "fix_verify": fv,
        "risk_rank": rr,
    }


def test_signals_agree_standard_fixture(standard_fixtures):
    """Test standard case: all signals agree on merge-with-patch."""
    f = standard_fixtures
    verdict = reconcile_verdict(
        f["version_diff"],
        f["vuln_lookup"],
        f["usage_impact"],
        f["fix_verify"],
        f["risk_rank"],
    )

    assert verdict["risk_tier"] == "merge-with-patch"
    assert verdict["has_patch"] is True
    assert "--- a/src/api/client.js" in verdict["patch"]
    assert len(verdict["findings"]) >= 2
    assert "## ![" in verdict["markdown_comment"]
    assert "npm test" in verdict["markdown_comment"]


def test_cve_downweighting_when_unreachable(standard_fixtures):
    """Test central Blast Radius innovation:

    A CVE flagged by vuln-lookup with zero reachable call sites reported by usage-impact
    should be DOWN-WEIGHTED in severity, not triggering do-not-merge.
    """
    f = standard_fixtures
    # Introduce a new high-severity CVE
    vuln_data = copy.deepcopy(f["vuln_lookup"])
    vuln_data["cves_introduced"] = [
        {
            "cve_id": "CVE-2024-99999",
            "ghsa_id": "GHSA-xxxx-yyyy-zzzz",
            "summary": "Hypothetical SSRF in unused sub-module",
            "severity": "critical",
            "cvss_score": 9.8,
            "affected_range": ">= 1.7.0",
            "fixed_in": "1.7.3",
            "advisory_url": "https://example.com/advisory",
        }
    ]

    # Usage impact reports ZERO call sites for this CVE or package
    usage_data = copy.deepcopy(f["usage_impact"])
    usage_data["impact_results"] = []  # No usages

    # Version diff with no breaking changes
    vd_data = copy.deepcopy(f["version_diff"])
    vd_data["breaking_changes"] = []

    # Fix verify with no patches needed
    fv_data = copy.deepcopy(f["fix_verify"])
    fv_data["patches"] = []

    verdict = reconcile_verdict(vd_data, vuln_data, usage_data, fv_data)

    # Risk should NOT be 'do-not-merge' because zero call sites were touched
    assert verdict["risk_tier"] == "safe"
    downweighted = [f for f in verdict["findings"] if f["finding_type"] == "cve_unreachable"]
    assert len(downweighted) == 1
    assert "down-weighted" in downweighted[0]["title"]
    assert downweighted[0]["reachable_call_sites"] == 0


def test_cve_reachable_triggers_do_not_merge(standard_fixtures):
    """A critical CVE introduced with active reachable call sites must trigger do-not-merge."""
    f = standard_fixtures
    vuln_data = copy.deepcopy(f["vuln_lookup"])
    vuln_data["cves_introduced"] = [
        {
            "cve_id": "CVE-2024-88888",
            "ghsa_id": None,
            "summary": "Remote Code Execution via request parser",
            "severity": "critical",
            "cvss_score": 9.9,
            "affected_range": ">= 1.7.0",
            "fixed_in": "1.7.3",
            "advisory_url": "https://example.com/cve-2024-88888",
        }
    ]

    usage_data = copy.deepcopy(f["usage_impact"])
    # Ensure there is an active reachable call site
    assert any(
        cs.get("reachable_from_untrusted_input")
        for ir in usage_data["impact_results"]
        for cs in ir["call_sites"]
    )

    verdict = reconcile_verdict(f["version_diff"], vuln_data, usage_data, f["fix_verify"])
    assert verdict["risk_tier"] == "do-not-merge"
    blocking = [f for f in verdict["findings"] if f["finding_type"] == "cve_reachable"]
    assert len(blocking) == 1


def test_malformed_subagent_output_fails_loudly(standard_fixtures):
    """Deliberately feed malformed fixtures to ensure the orchestrator fails loudly."""
    f = standard_fixtures

    # 1. Missing required field in version_diff
    bad_vd = copy.deepcopy(f["version_diff"])
    del bad_vd["breaking_changes"]

    with pytest.raises(MergeEngineError) as exc_info:
        reconcile_verdict(bad_vd, f["vuln_lookup"], f["usage_impact"], f["fix_verify"])
    assert "Validation failed for subagent 'version-diff'" in str(exc_info.value)

    # 2. Invalid data type in vuln_lookup
    bad_vl = copy.deepcopy(f["vuln_lookup"])
    bad_vl["cves_closed"] = "not_a_list"

    with pytest.raises(MergeEngineError) as exc_info:
        reconcile_verdict(f["version_diff"], bad_vl, f["usage_impact"], f["fix_verify"])
    assert "Validation failed for subagent 'vuln-lookup'" in str(exc_info.value)


def test_breaking_change_without_patch_triggers_do_not_merge(standard_fixtures):
    """Breaking change requiring manual review (no mechanical fix) triggers do-not-merge."""
    f = standard_fixtures
    fv_data = copy.deepcopy(f["fix_verify"])
    # Modify patch to be manual_review_required
    fv_data["patches"][0]["patch_type"] = "manual_review_required"
    fv_data["patches"][0]["diff"] = None
    fv_data["patches"][0]["manual_review_reason"] = "Complex architectural redesign required"
    fv_data["total_mechanical_fixes"] = 0
    fv_data["total_manual_review"] = 1

    verdict = reconcile_verdict(f["version_diff"], f["vuln_lookup"], f["usage_impact"], fv_data)
    assert verdict["risk_tier"] == "do-not-merge"
    assert verdict["has_patch"] is False
    assert "manual review" in verdict["summary"].lower()


def test_clean_safe_bump(standard_fixtures):
    """A bump with no breaking changes and no active CVEs results in safe."""
    f = standard_fixtures
    vd = copy.deepcopy(f["version_diff"])
    vd["breaking_changes"] = []
    vd["deprecations"] = []

    vl = copy.deepcopy(f["vuln_lookup"])
    vl["cves_introduced"] = []
    vl["cves_unresolved"] = []

    ui = copy.deepcopy(f["usage_impact"])
    ui["impact_results"] = []

    fv = copy.deepcopy(f["fix_verify"])
    fv["patches"] = []
    fv["total_mechanical_fixes"] = 0

    verdict = reconcile_verdict(vd, vl, ui, fv)
    assert verdict["risk_tier"] == "safe"
    assert verdict["has_patch"] is False
    assert "Safe to merge" in verdict["recommended_action"]
