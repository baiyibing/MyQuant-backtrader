import hashlib, json
from pathlib import Path

def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(8*1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

out = Path(r'D:\PycharmProjects\MyQuant-backtrader\backtest_output\joint-return-v1-replay-panel-phase\out-v2-pack-spans-cheap-bar-decimal\joint-return-control-only-50-5-narrow-clock-patch-614')
live = Path(r'D:\PycharmProjects\MyQuant-backtrader\backtest_output\joint-return-v1-replay-panel-phase\out-v2-pack-spans-live-universe\joint-return-control-only-50-5-narrow-clock-patch-614')
req_fills = 'd6d40bc4979d462582a8c53c34591cdcca6fafd123857da9d7053aa598fe3376'
req_nav = '2cf88d08b7f50c6c54cdcb8ba64a4fb96024262f988c18d8b025259d1c572685'
files = ['fills.csv', 'daily_nav.csv']
result = {}
for name in files:
    a = out / name
    b = live / name
    sa = sha256(a)
    sb = sha256(b) if b.exists() else None
    # byte compare
    identical = False
    if b.exists() and a.stat().st_size == b.stat().st_size:
        identical = True
        with open(a,'rb') as fa, open(b,'rb') as fb:
            while True:
                ca = fa.read(8*1024*1024)
                cb = fb.read(8*1024*1024)
                if ca != cb:
                    identical = False
                    break
                if not ca:
                    break
    result[name] = {
        'sha256': sa,
        'size': a.stat().st_size,
        'live_sha256': sb,
        'byte_identical_vs_live': identical,
        'matches_required': sa == (req_fills if name=='fills.csv' else req_nav),
    }
# summary replay_source
summary = json.loads((out/'summary.json').read_text(encoding='utf-8'))
result['replay_source_sha256'] = summary.get('replay_source_sha256') or summary.get('source_sha256')
# dig deeper for key
def find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj: return obj[key]
        for v in obj.values():
            r = find_key(v, key)
            if r is not None: return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_key(v, key)
            if r is not None: return r
    return None
result['replay_source_sha256_found'] = find_key(summary, 'replay_source_sha256')
result['status'] = summary.get('status')
print(json.dumps(result, indent=2))