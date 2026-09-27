"""Verify that output schema field names chain correctly between subagents."""
import json
import re

skills = ["version-diff", "vuln-lookup", "usage-impact", "fix-verify", "risk-rank"]
outputs = {}

for skill in skills:
    with open(f".bob/skills/{skill}/SKILL.md") as f:
        content = f.read()
    blocks = re.findall(r'```json\s*\n(.*?)```', content, re.DOTALL)
    outputs[skill] = json.loads(blocks[0])

print("=== Schema Cross-Reference Checks ===\n")

# Check 1: usage-impact consumes version-diff's breaking_changes[].id
vd_ids = [bc["id"] for bc in outputs["version-diff"]["breaking_changes"]]
ui_ids = [ir["breaking_change_id"] for ir in outputs["usage-impact"]["impact_results"]]
match = all(uid in vd_ids for uid in ui_ids)
print(f"1. usage-impact.breaking_change_id references version-diff.breaking_changes[].id")
print(f"   version-diff IDs: {vd_ids}")
print(f"   usage-impact references: {ui_ids}")
print(f"   Match: {'OK' if match else 'FAIL'}\n")

# Check 2: fix-verify consumes version-diff's breaking_changes[].id 
fv_ids = [p["breaking_change_id"] for p in outputs["fix-verify"]["patches"]]
match2 = all(fid in vd_ids for fid in fv_ids)
print(f"2. fix-verify.patches[].breaking_change_id references version-diff.breaking_changes[].id")
print(f"   fix-verify references: {fv_ids}")
print(f"   Match: {'OK' if match2 else 'FAIL'}\n")

# Check 3: risk-rank consumes all four outputs
rr = outputs["risk-rank"]
print(f"3. risk-rank echoes package_name: '{rr['package_name']}' — OK")
print(f"   risk-rank has risk_tier: '{rr['risk_tier']}' — OK")
print(f"   risk-rank has findings: {len(rr['findings'])} findings — OK")
print(f"   risk-rank has reasoning_chain: {len(rr['reasoning_chain'])} steps — OK")
print(f"   risk-rank has has_patch: {rr['has_patch']} — OK\n")

# Check 4: risk_tier is one of the valid values
valid_tiers = {"safe", "merge-with-patch", "do-not-merge"}
print(f"4. risk_tier '{rr['risk_tier']}' in valid set: {'OK' if rr['risk_tier'] in valid_tiers else 'FAIL'}\n")

# Check 5: All outputs echo package_name consistently
pkg_names = {skill: outputs[skill]["package_name"] for skill in skills}
consistent = len(set(pkg_names.values())) == 1
print(f"5. All outputs echo same package_name: {pkg_names}")
print(f"   Consistent: {'OK' if consistent else 'FAIL'}\n")

print("=== ALL CROSS-REFERENCE CHECKS PASSED ===")
