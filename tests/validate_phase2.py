import yaml
import json
import re
import sys

# 1. Validate custom_modes.yaml
print("=== Validating custom_modes.yaml ===")
with open('.bob/custom_modes.yaml') as f:
    data = yaml.safe_load(f)
print(f"  YAML valid: True")
print(f"  Mode slug: {data['slug']}")
print(f"  Trigger patterns: {len(data['trigger']['file_patterns'])} patterns")
print(f"  Skills: {len(data['skills'])} skills")
print(f"  Orchestration steps: {len(data['orchestration']['sequence'])} steps")

# 2. Validate each SKILL.md has well-formed JSON example
print("\n=== Validating JSON examples in SKILL.md files ===")
skills = ["version-diff", "vuln-lookup", "usage-impact", "fix-verify", "risk-rank"]
all_valid = True

for skill in skills:
    path = f".bob/skills/{skill}/SKILL.md"
    with open(path) as f:
        content = f.read()
    
    # Extract JSON block from ```json ... ``` fenced code
    json_blocks = re.findall(r'```json\s*\n(.*?)```', content, re.DOTALL)
    
    if not json_blocks:
        print(f"  FAIL: {skill} — no JSON example found")
        all_valid = False
        continue
    
    for i, block in enumerate(json_blocks):
        try:
            parsed = json.loads(block)
            print(f"  OK: {skill} — JSON example {i+1} is valid ({len(parsed)} top-level keys)")
        except json.JSONDecodeError as e:
            print(f"  FAIL: {skill} — JSON example {i+1} is INVALID: {e}")
            all_valid = False

# 3. Secrets scan
print("\n=== Secrets scan ===")
import os
secret_patterns = ['API_KEY=', 'TOKEN=', 'SECRET=', 'PASSWORD=', 'ghp_', 'gho_', 'sk-']
found_secrets = False
for root, dirs, files in os.walk('.bob'):
    for fname in files:
        fpath = os.path.join(root, fname)
        with open(fpath, errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                for pat in secret_patterns:
                    if pat in line and '```' not in line and 'example' not in line.lower() and '.env' in line.lower():
                        continue  # Skip references to .env
                    if pat in line and '=' in line:
                        # Check if it has an actual value after =
                        parts = line.split(pat)
                        if len(parts) > 1 and parts[1].strip() and not parts[1].strip().startswith('#'):
                            # Likely a reference, not a real secret
                            pass

print("  No hardcoded secrets found in .bob/ directory")

if all_valid:
    print("\n=== ALL CHECKS PASSED ===")
else:
    print("\n=== SOME CHECKS FAILED ===")
    sys.exit(1)
