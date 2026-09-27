"""Blast Radius — Orchestrator Merge & Report Engine.

Ingests the five subagent JSON outputs, validates against JSON schemas,
reconciles risk signals (including down-weighting uncalled CVEs),
and renders structured verdicts and GitHub PR review comments.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import jsonschema

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "schemas"


class MergeEngineError(Exception):
    """Raised when subagent outputs fail validation or reconciliation."""


def load_schema(schema_name: str) -> dict:
    """Load JSON Schema from the schemas directory."""
    schema_path = SCHEMAS_DIR / f"{schema_name}.schema.json"
    if not schema_path.is_file():
        raise MergeEngineError(f"Missing schema file: {schema_path}")
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_subagent_output(name: str, data: dict) -> None:
    """Validate a single subagent dictionary against its schema."""
    schema = load_schema(name)
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as err:
        raise MergeEngineError(
            f"Validation failed for subagent '{name}': {err.message} at path {list(err.path)}"
        ) from err


def reconcile_verdict(
    version_diff: dict,
    vuln_lookup: dict,
    usage_impact: dict,
    fix_verify: dict,
    risk_rank: Optional[dict] = None,
) -> dict:
    """Reconcile the signals from all subagents into a unified risk verdict.

    Special attention is paid to reachability and down-weighting:
    - CVEs with 0 call sites reported are down-weighted in risk.
    - Breaking changes with mechanical patches available yield 'merge-with-patch'.
    - Breaking changes with reachable call sites and no mechanical fix yield 'do-not-merge'.
    - Clean bumps (or only closed CVEs + no unpatched breaking changes) yield 'safe'.
    """
    # 1. Validate all incoming subagents
    validate_subagent_output("version-diff", version_diff)
    validate_subagent_output("vuln-lookup", vuln_lookup)
    validate_subagent_output("usage-impact", usage_impact)
    validate_subagent_output("fix-verify", fix_verify)
    if risk_rank:
        validate_subagent_output("risk-rank", risk_rank)

    pkg = version_diff["package_name"]
    old_ver = version_diff["old_version"]
    new_ver = version_diff["new_version"]
    ecosystem = version_diff["ecosystem"]

    # Map impact results by breaking_change_id
    impact_map = {
        item["breaking_change_id"]: item
        for item in usage_impact.get("impact_results", [])
    }

    # Map patches by breaking_change_id
    patch_map = {
        p["breaking_change_id"]: p
        for p in fix_verify.get("patches", [])
    }

    findings: List[dict] = []
    reasoning: List[str] = []

    # 2. Analyze closed CVEs (Positive Signal)
    closed_cves = vuln_lookup.get("cves_closed", [])
    for cve in closed_cves:
        findings.append({
            "finding_type": "cve_closed",
            "severity": "info",
            "title": f"{cve['cve_id']} resolved",
            "description": f"{cve['summary']} (Fixed in {cve['fixed_in']}).",
            "references": [cve["cve_id"]] + ([cve["ghsa_id"]] if cve.get("ghsa_id") else []),
            "reachable_call_sites": 0,
            "total_call_sites": 0,
        })
        reasoning.append(
            f"Vulnerability {cve['cve_id']} ({cve['severity']} severity) is resolved by {new_ver}."
        )

    # 3. Analyze introduced or unresolved CVEs
    introduced_cves = vuln_lookup.get("cves_introduced", [])
    unresolved_cves = vuln_lookup.get("cves_unresolved", [])
    has_blocking_cve = False

    for cve in introduced_cves + unresolved_cves:
        # Check call sites in usage-impact (if reported for the CVE or general package usage)
        total_sites = 0
        reachable_sites = 0
        for impact in usage_impact.get("impact_results", []):
            total_sites += impact.get("call_site_count", 0)
            for cs in impact.get("call_sites", []):
                if cs.get("reachable_from_untrusted_input"):
                    reachable_sites += 1

        if total_sites == 0 or reachable_sites == 0:
            # DOWN-WEIGHTING CASE: CVE exists, but zero reachable call sites in target codebase
            findings.append({
                "finding_type": "cve_unreachable",
                "severity": "low",
                "title": f"{cve['cve_id']} introduced but unreachable (down-weighted)",
                "description": (
                    f"{cve['summary']} Severity {cve['severity']} down-weighted: "
                    f"zero reachable call sites identified in repository."
                ),
                "references": [cve["cve_id"]],
                "reachable_call_sites": reachable_sites,
                "total_call_sites": total_sites,
            })
            reasoning.append(
                f"{cve['cve_id']} ({cve['severity']}) has zero reachable call sites in this repository. Down-weighting risk."
            )
        else:
            # High risk: CVE introduced and code is actively reachable
            has_blocking_cve = True
            findings.append({
                "finding_type": "cve_reachable",
                "severity": "critical" if cve["severity"] == "critical" else "high",
                "title": f"{cve['cve_id']} actively reachable in codebase",
                "description": f"{cve['summary']} Found {reachable_sites} reachable call site(s).",
                "references": [cve["cve_id"]],
                "reachable_call_sites": reachable_sites,
                "total_call_sites": total_sites,
            })
            reasoning.append(
                f"{cve['cve_id']} is actively reachable at {reachable_sites} call site(s). High danger."
            )

    # 4. Analyze Breaking Changes & Patchability
    breaking_changes = version_diff.get("breaking_changes", [])
    has_unfixable_breaking_change = False
    has_patchable_breaking_change = False
    unified_diffs: List[str] = []
    files_modified: List[str] = []
    test_commands: List[str] = []

    for bc in breaking_changes:
        bc_id = bc["id"]
        impact = impact_map.get(bc_id)
        call_sites = impact.get("call_sites", []) if impact else []
        site_count = impact.get("call_site_count", 0) if impact else 0
        reachable_count = sum(1 for cs in call_sites if cs.get("reachable_from_untrusted_input"))

        if site_count == 0:
            # Breaking change with 0 call sites -> no impact
            findings.append({
                "finding_type": "breaking_change_no_impact",
                "severity": "info",
                "title": f"{bc_id}: {bc['affected_api']} (0 call sites)",
                "description": f"{bc['description']} No usages found in repository.",
                "references": [bc_id],
                "reachable_call_sites": 0,
                "total_call_sites": 0,
            })
            reasoning.append(f"Breaking change {bc_id} has 0 call sites in repository — non-issue.")
            continue

        patch = patch_map.get(bc_id)
        if patch and patch.get("patch_type") == "mechanical_fix" and patch.get("diff"):
            has_patchable_breaking_change = True
            unified_diffs.append(patch["diff"])
            files_modified.extend(patch.get("files_modified", []))
            test_commands.extend(patch.get("test_commands", []))

            findings.append({
                "finding_type": "breaking_change_fixable",
                "severity": "medium",
                "title": f"{bc_id}: {bc['affected_api']} (Patch available)",
                "description": f"{bc['description']} Found {site_count} call site(s) ({reachable_count} reachable). Mechanical patch provided.",
                "references": [bc_id],
                "reachable_call_sites": reachable_count,
                "total_call_sites": site_count,
            })
            reasoning.append(
                f"Breaking change {bc_id} affects {site_count} call site(s). Mechanical patch is available."
            )
        else:
            has_unfixable_breaking_change = True
            findings.append({
                "finding_type": "breaking_change_manual",
                "severity": "high",
                "title": f"{bc_id}: {bc['affected_api']} requires manual review",
                "description": f"{bc['description']} Found {site_count} call site(s). No automated patch available.",
                "references": [bc_id],
                "reachable_call_sites": reachable_count,
                "total_call_sites": site_count,
            })
            reasoning.append(
                f"Breaking change {bc_id} affects {site_count} call site(s) and requires manual intervention."
            )

    # 5. Determine Overall Risk Tier
    if has_blocking_cve and has_unfixable_breaking_change:
        tier = "do-not-merge"
        confidence = 0.95
        rec_action = "Do not merge. Critical security vulnerabilities and breaking changes requiring manual review detected."
    elif has_blocking_cve:
        tier = "do-not-merge"
        confidence = 0.92
        rec_action = "Do not merge. Active security vulnerability reachable from untrusted input."
    elif has_unfixable_breaking_change:
        tier = "do-not-merge"
        confidence = 0.90
        rec_action = "Do not merge. Breaking changes detected with active call sites that require manual review."
    elif has_patchable_breaking_change:
        tier = "merge-with-patch"
        confidence = 0.88
        rec_action = "Apply the attached patch, run verification tests, then merge."
    else:
        tier = "safe"
        confidence = 0.95
        rec_action = "Safe to merge immediately. No active CVEs or breaking call sites detected."

    # If risk-rank was supplied and aligns, preserve its high-level wording
    if risk_rank and risk_rank.get("risk_tier") == tier:
        summary = risk_rank.get("summary", "")
        if risk_rank.get("confidence"):
            confidence = float(risk_rank["confidence"])
    else:
        summary = (
            f"Bumping {pkg} from {old_ver} to {new_ver} ({ecosystem}): "
            f"Assessed as '{tier}'. "
            f"{len(closed_cves)} CVE(s) closed, {len(findings)} total finding(s). "
            f"{rec_action}"
        )

    # Deduplicate lists
    files_modified = sorted(list(set(files_modified)))
    test_commands = sorted(list(set(test_commands)))
    full_patch = "\n".join(unified_diffs) if unified_diffs else None

    verdict = {
        "package_name": pkg,
        "old_version": old_ver,
        "new_version": new_ver,
        "ecosystem": ecosystem,
        "risk_tier": tier,
        "confidence": confidence,
        "summary": summary,
        "findings": findings,
        "reasoning_chain": reasoning,
        "recommended_action": rec_action,
        "has_patch": bool(full_patch),
        "patch": full_patch,
        "files_modified": files_modified,
        "test_commands": test_commands,
    }

    verdict["markdown_comment"] = render_markdown_comment(verdict)
    return verdict


def render_markdown_comment(verdict: dict) -> str:
    """Render a structured verdict as a clean, publication-ready GitHub PR review comment."""
    tier = verdict["risk_tier"]
    badge_map = {
        "safe": "![Safe](https://img.shields.io/badge/Blast%20Radius-SAFE-brightgreen)",
        "merge-with-patch": "![Merge With Patch](https://img.shields.io/badge/Blast%20Radius-MERGE%20WITH%20PATCH-orange)",
        "do-not-merge": "![Do Not Merge](https://img.shields.io/badge/Blast%20Radius-DO%20NOT%20MERGE-red)",
    }
    badge = badge_map.get(tier, tier.upper())

    lines = [
        f"## {badge}",
        "",
        f"**Package:** `{verdict['package_name']}` | **Delta:** `{verdict['old_version']}` → `{verdict['new_version']}` (`{verdict['ecosystem']}`)",
        f"**Risk Tier:** `{verdict['risk_tier'].upper()}` | **Confidence:** `{int(verdict['confidence'] * 100)}%`",
        "",
        "### Verdict Summary",
        verdict["summary"],
        "",
        "### Evidence & Findings",
        "| Severity | Finding | Reachability | References |",
        "|:---|:---|:---|:---|",
    ]

    for f in verdict["findings"]:
        ref_str = ", ".join(f"`{r}`" for r in f["references"]) or "N/A"
        reach_str = f"{f['reachable_call_sites']}/{f['total_call_sites']} call sites" if f["total_call_sites"] > 0 else "N/A"
        sev_icon = {
            "critical": "🛑 Critical",
            "high": "🔴 High",
            "medium": "🟡 Medium",
            "low": "🟢 Low",
            "info": "ℹ️ Info",
        }.get(f["severity"], f["severity"].capitalize())
        lines.append(f"| {sev_icon} | **{f['title']}**<br>{f['description']} | {reach_str} | {ref_str} |")

    lines.append("")
    lines.append("### Reasoning Chain")
    for step in verdict["reasoning_chain"]:
        lines.append(f"- {step}")

    lines.append("")
    lines.append("### Recommended Action")
    lines.append(f"> {verdict['recommended_action']}")

    if verdict["has_patch"] and verdict.get("patch"):
        lines.append("")
        lines.append("### Suggested Patch (Unified Diff)")
        lines.append("```diff")
        lines.append(verdict["patch"].strip())
        lines.append("```")
        if verdict.get("test_commands"):
            lines.append("")
            lines.append("**Verification commands to run after applying:**")
            lines.append("```bash")
            for cmd in verdict["test_commands"]:
                lines.append(cmd)
            lines.append("```")

    lines.append("")
    lines.append("---")
    lines.append("*Generated automatically by **Blast Radius** — Evidence-Grounded Dependency Reviewer.*")

    return "\n".join(lines)


def load_fixtures_from_dir(fixtures_dir: Path) -> Tuple[dict, dict, dict, dict, Optional[dict]]:
    """Load the 5 subagent output JSONs from a directory or evidence subfolders."""
    def find_subagent_file(name: str) -> Optional[Path]:
        # 1. Flat file: dir/name.json
        direct_path = fixtures_dir / f"{name}.json"
        if direct_path.is_file():
            return direct_path
        # 2. Subfolder: dir/name/name.json or first .json in dir/name/
        subfolder = fixtures_dir / name
        if subfolder.is_dir():
            exact_sub = subfolder / f"{name}.json"
            if exact_sub.is_file():
                return exact_sub
            json_candidates = [p for p in subfolder.glob("*.json") if p.name != "validation_report.json"]
            if json_candidates:
                return sorted(json_candidates)[0]
        return None

    def load_json(name: str) -> dict:
        path = find_subagent_file(name)
        if not path:
            raise MergeEngineError(f"Required subagent output missing for '{name}' in {fixtures_dir}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    vd = load_json("version-diff")
    vl = load_json("vuln-lookup")
    ui = load_json("usage-impact")
    fv = load_json("fix-verify")

    rr = None
    rr_file = find_subagent_file("risk-rank")
    if rr_file:
        with open(rr_file, "r", encoding="utf-8") as f:
            rr = json.load(f)

    return vd, vl, ui, fv, rr


def main() -> None:
    """CLI entrypoint for running the merge engine."""
    parser = argparse.ArgumentParser(description="Blast Radius Orchestrator Merge Engine")
    parser.add_argument(
        "--fixtures-dir",
        type=str,
        default="fixtures",
        help="Directory containing the 5 subagent JSON files (default: fixtures)",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default="evidence/verdict.json",
        help="Path to write verdict JSON (default: evidence/verdict.json)",
    )
    parser.add_argument(
        "--output-md",
        type=str,
        default="evidence/verdict.md",
        help="Path to write verdict Markdown PR comment (default: evidence/verdict.md)",
    )
    args = parser.parse_args()

    fixtures_path = Path(args.fixtures_dir)
    print(f"Loading subagent outputs from: {fixtures_path}")

    try:
        vd, vl, ui, fv, rr = load_fixtures_from_dir(fixtures_path)
        verdict = reconcile_verdict(vd, vl, ui, fv, rr)

        print(f"\nReconciliation complete:")
        print(f"  Package: {verdict['package_name']} ({verdict['old_version']} -> {verdict['new_version']})")
        print(f"  Risk Tier: {verdict['risk_tier'].upper()}")
        print(f"  Confidence: {verdict['confidence'] * 100:.1f}%")
        print(f"  Has Patch: {verdict['has_patch']}")

        # Ensure output directories exist
        out_json_path = Path(args.output_json)
        out_md_path = Path(args.output_md)
        out_json_path.parent.mkdir(parents=True, exist_ok=True)
        out_md_path.parent.mkdir(parents=True, exist_ok=True)

        with open(out_json_path, "w", encoding="utf-8") as f:
            json.dump(verdict, f, indent=2)
        print(f"  Saved verdict JSON to {out_json_path}")

        with open(out_md_path, "w", encoding="utf-8") as f:
            f.write(verdict["markdown_comment"])
        print(f"  Saved Markdown PR comment to {out_md_path}")

    except MergeEngineError as err:
        print(f"\nERROR: Merge engine failed: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
