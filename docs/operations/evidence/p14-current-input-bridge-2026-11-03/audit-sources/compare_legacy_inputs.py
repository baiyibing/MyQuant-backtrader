import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser(description='Compare frozen legacy and current industry market inputs without dropping fields.')
parser.add_argument('--repo-root', required=True, type=Path)
parser.add_argument('--legacy-recipe', required=True, type=Path)
parser.add_argument('--industry-recipe', required=True, type=Path)
parser.add_argument('--out', required=True, type=Path)
args = parser.parse_args()
ROOT = args.repo_root.resolve()
OLD = args.legacy_recipe
NEW = args.industry_recipe
legacy = json.loads(OLD.read_text(encoding='utf-8'))
industry = json.loads(NEW.read_text(encoding='utf-8'))
prefixes = [(str(ROOT).replace('\\', '/'), '$REPO'),
            (os.environ['OSKH_SOURCE_PARQUET_ROOT'].replace('\\', '/'), '$LAKE')]

def canonical(value):
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in value.items()}
    if isinstance(value, list):
        return [canonical(v) for v in value]
    if isinstance(value, str):
        text = value.replace('\\', '/')
        for prefix, alias in prefixes:
            if text.casefold() == prefix.casefold() or text.casefold().startswith(prefix.casefold() + '/'):
                return alias + text[len(prefix):]
        return text
    return value

left, right = canonical(legacy['inputs']), canonical(industry['inputs'])
facts = {}
for family in ['csv_minute', 'v7']:
    facts[family] = {key: left[family][key] == right[family][key] for key in left[family]}
diff_paths = subprocess.check_output(['git','diff','--name-only',legacy['code_sha'], industry['code_sha']], cwd=ROOT, text=True).splitlines()
proof = {
    'audit_runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'legacy_code_sha': legacy['code_sha'], 'industry_code_sha': industry['code_sha'],
    'code_delta_only_under_docs': all(p.startswith('docs/') for p in diff_paths),
    'input_fields_equal': facts,
    'whole_inputs_equal_after_only_root_alias_normalization': left == right,
    'normalization': 'Windows slash normalization and only resolved repository/source prefix aliases; no field/hash/value exclusions',
    'claim': 'Market input/code bridge only; final industry matrix verdict required before acceptance',
}
args.out.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(proof,ensure_ascii=False))
