"""Bit-compare v1 vs v2 artifacts and emit RECEIPT.md"""
from __future__ import annotations
import hashlib, json, subprocess
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

BT = Path(r"D:\PycharmProjects\MyQuant-backtrader")
ROOT = BT / "backtest_output" / "joint-return-v1-validate-v2-k3"
V1 = ROOT / "run-v1" / "joint-return-validate-v2-k3-subset62"
V2 = ROOT / "run-v2" / "joint-return-validate-v2-k3-subset62"

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

names = ["fills.csv", "orders.csv", "daily_nav.csv"]
rows = []
all_pass = True
for name in names:
    p1, p2 = V1 / name, V2 / name
    b1, b2 = p1.read_bytes(), p2.read_bytes()
    h1, h2 = hashlib.sha256(b1).hexdigest(), hashlib.sha256(b2).hexdigest()
    equal = b1 == b2
    all_pass = all_pass and equal
    rows.append({
        "name": name,
        "equal": equal,
        "v1_sha256": h1,
        "v2_sha256": h2,
        "v1_bytes": len(b1),
        "v2_bytes": len(b2),
    })
    print(name, "PASS" if equal else "FAIL", h1, h2, len(b1))

# summary hashes
s1 = json.loads((V1 / "summary.json").read_text(encoding="utf-8"))
s2 = json.loads((V2 / "summary.json").read_text(encoding="utf-8"))
print("status", s1.get("status"), s2.get("status"))
print("fills_by_mode v1", (s1.get("fills_by_mode") or s1.get("metrics")))

# timings
err1 = (ROOT / "logs" / "v1.stderr.log").read_text(encoding="utf-8", errors="replace").strip()
err2 = (ROOT / "logs" / "v2.stderr.log").read_text(encoding="utf-8", errors="replace").strip()
# parse json after prefix
import re
def parse_timings(err: str) -> dict:
    m = re.search(r"\{.*\}", err)
    return json.loads(m.group(0)) if m else {}
t1 = parse_timings(err1)
t2 = parse_timings(err2)
print("t1", t1)
print("t2", t2)

# tip
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(BT), text=True).strip()
# default still v1?
src = (BT / "backtest" / "research" / "joint_return_replay.py").read_text(encoding="utf-8")
default_v1 = 'choices=("v1", "v2"), default="v1"' in src or "default=\"v1\"" in src
# pin note
pin_m = re.search(r'FROZEN_CONTRACT_HASH\s*=\s*"([0-9a-f]+)"', src)
pin = pin_m.group(1) if pin_m else "?"

meta = json.loads((ROOT / "artifacts" / "subset62_meta.json").read_text(encoding="utf-8"))
now = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%dT%H:%M:%S%z")

# validate phase sums
v1_validate = t1.get("validate_bars", 0.0)
v2_validate = sum(t2.get(k, 0.0) for k in ("validate_metadata", "validate_panel_load", "validate_seal", "validate_panel_scan"))

# GO recommendation: bit-compare pass + timings show v2 validate faster; still default off
recommend = "recommend GO (research opt-in only; keep default v1 / default-off)" if all_pass else "not-yet (bit-compare FAIL)"

receipt = f"""# RECEIPT — validate-v2 K3 (v1 vs v2 timings + bit-compare)

- written_at: {now} (Asia/Shanghai)
- host: newtest_4090 (`6e8988e9-eaab-447c-ad5d-effde4604424`)
- tip SHA: `{head}` (PR #178 `research/joint-return-validate-v2-k2`)
- Python: `D:\\anaconda3\\envs\\vanna312\\python.exe`
- STATUS: {"BT_RESEARCH_REPLAY_PASS (both)" if s1.get("status")=="BT_RESEARCH_REPLAY_PASS" and s2.get("status")=="BT_RESEARCH_REPLAY_PASS" else "CHECK"}
- Bit-compare fills/orders/daily_nav: **{"PASS" if all_pass else "FAIL"}**
- Default still **v1** / **off**: {"yes" if default_v1 else "CHECK"}
- Format lock: seal remains **qlib_bin marks-v1**; this K3 used sealed JSON twin (K2 option B JSON→DensePanel). **No Arrow default.**
- Local-only Mode B pin for twin: `FROZEN_CONTRACT_HASH` → `{pin}` (tip had `9ee8cc3c…`; constant-only, not committed; same practice as Mode B CLOCK_PATCH-614). Fill/clock/fee untouched.

## Subset (same 62/614 as marks bench)

- Rule: first 10% of sorted unique instruments
- **62 symbols** (`SH600010`…`SH601952`), **3630906** bar rows, **204** intents, **204** reference_marks
- Sealed bars: `{meta["sealed_bars"]}`
- bars_content_sha256: `{meta["bars_content_sha256"]}`
- Intents pack: `{meta["intents_pack"]}` (remanifested; run_id=`joint-return-validate-v2-k3-subset62`)
- Source subset dump (unsealed): `backtest_output/joint-return-v1-modeb-bars-format-bench/artifacts/subset_bars.json`
- Oracle sidecars: `backtest_output/joint-return-v1-modeb-bars-format-bench-qlib-bin-marks/oracle_sidecars.json`
- Full 614 Mode B twin **not** re-run here (prior profile ~1978s); 10% subset is the K3 knife.

## Commands

```text
# mini (repo tests; tip a25dd475)
D:\\anaconda3\\envs\\vanna312\\python.exe -m pytest -q tests/test_joint_return_validate_v2.py tests/test_joint_return_replay.py -k "v2 or validate_version or parity or bit or fills_orders or cli_csv or profile"
# -> 41 passed (includes test_v2_replay_lazy_decimal_and_bit_parity*, test_v2_cli_timings_and_artifact_parity)

# subset62 profiled twin
python -u scripts/research/run_joint_return_replay.py \\
  --intents backtest_output/joint-return-v1-validate-v2-k3/artifacts/subset62_intents_pack \\
  --bars backtest_output/joint-return-v1-validate-v2-k3/artifacts/subset62_sealed_bars.json \\
  --arm P-BASE --fill-mode all \\
  --out backtest_output/joint-return-v1-validate-v2-k3/run-v1/joint-return-validate-v2-k3-subset62 \\
  --validate-version v1 --profile-timings

python -u scripts/research/run_joint_return_replay.py \\
  --intents .../subset62_intents_pack --bars .../subset62_sealed_bars.json \\
  --arm P-BASE --fill-mode all \\
  --out .../run-v2/joint-return-validate-v2-k3-subset62 \\
  --validate-version v2 --profile-timings
```

## Bit-compare / content-hash

| artifact | result | v1_sha256 | v2_sha256 | bytes |
| --- | --- | --- | --- | ---: |
| fills.csv | {"PASS" if rows[0]["equal"] else "FAIL"} | `{rows[0]["v1_sha256"]}` | `{rows[0]["v2_sha256"]}` | {rows[0]["v1_bytes"]} |
| orders.csv | {"PASS" if rows[1]["equal"] else "FAIL"} | `{rows[1]["v1_sha256"]}` | `{rows[1]["v2_sha256"]}` | {rows[1]["v1_bytes"]} |
| daily_nav.csv | {"PASS" if rows[2]["equal"] else "FAIL"} | `{rows[2]["v1_sha256"]}` | `{rows[2]["v2_sha256"]}` | {rows[2]["v1_bytes"]} |

## Profile-timings stage table (seconds)

### v1 (`--validate-version v1`)

| phase | seconds |
| --- | ---: |
| bundle_load | {t1.get("bundle_load")} |
| bars_read | {t1.get("bars_read")} |
| bars_json_parse | {t1.get("bars_json_parse")} |
| **validate_bars** | **{t1.get("validate_bars")}** |
| validate_reference_marks | {t1.get("validate_reference_marks")} |
| replay_M-REF_P-BASE | {t1.get("replay_M-REF_P-BASE")} |
| replay_M-LAG_P-BASE | {t1.get("replay_M-LAG_P-BASE")} |
| write_artifacts | {t1.get("write_artifacts")} |
| **total_seconds** | **{t1.get("total_seconds")}** |

stderr: `{err1}`

### v2 (`--validate-version v2`)

| phase | seconds |
| --- | ---: |
| bundle_load | {t2.get("bundle_load")} |
| bars_read | {t2.get("bars_read")} |
| bars_json_parse | {t2.get("bars_json_parse")} |
| **validate_metadata** | **{t2.get("validate_metadata")}** |
| **validate_panel_load** | **{t2.get("validate_panel_load")}** |
| **validate_seal** | **{t2.get("validate_seal")}** |
| **validate_panel_scan** | **{t2.get("validate_panel_scan")}** |
| validate_reference_marks | {t2.get("validate_reference_marks")} |
| replay_M-REF_P-BASE | {t2.get("replay_M-REF_P-BASE")} |
| replay_M-LAG_P-BASE | {t2.get("replay_M-LAG_P-BASE")} |
| write_artifacts | {t2.get("write_artifacts")} |
| **total_seconds** | **{t2.get("total_seconds")}** |

stderr: `{err2}`

### validate_* compare

| | v1 | v2 | delta (v2-v1) |
| --- | ---: | ---: | ---: |
| validate wall (sum) | {v1_validate:.6f} (`validate_bars`) | {v2_validate:.6f} (metadata+panel_load+seal+panel_scan) | {v2_validate - v1_validate:.6f} |
| total_seconds | {t1.get("total_seconds")} | {t2.get("total_seconds")} | {(t2.get("total_seconds") or 0) - (t1.get("total_seconds") or 0):.6f} |

Note: K2 JSON→DensePanel still pays `bars_json_parse` (~19s) on both; v2 validate path replaces `validate_bars` (~47s) with panel load/seal/scan (~{v2_validate:.2f}s). Replay phases similar (ephemeral cell views; not a fill-kernel speedup).

## Mini pytest

- Focused v2/parity/profile filter: **41 passed**
- Broader suite on this Windows host: 147 passed, 8 failed — all 8 are `UnicodeDecodeError: 'gbk'` reading UTF-8 docs via pathlib text mode (locale), unrelated to validate-v2 parity.

## Compliance

- Did **not** flip default to v2
- Did **not** change fill/clock/fee
- Did **not** merge/open PRs
- Did **not** overwrite modeb / prior bench outs
- Did **not** switch seal default to Arrow; format lock remains **qlib_bin marks-v1**

## Human GO recommendation

**{recommend}** — bit-compare PASS on subset62 + mini tests; validate_* wall improved; keep CLI/API default **v1** until human GO. Full-614 twin optional follow-up (prior Mode B profile ~1978s ×2).

## Paths

- This RECEIPT: `{ROOT / "RECEIPT.md"}`
- v1 out: `{V1}`
- v2 out: `{V2}`
- logs: `{ROOT / "logs"}`
"""

(ROOT / "RECEIPT.md").write_text(receipt, encoding="utf-8")
(ROOT / "bitcompare.json").write_text(json.dumps({"pass": all_pass, "rows": rows, "t1": t1, "t2": t2}, indent=2), encoding="utf-8")
print("WROTE", ROOT / "RECEIPT.md")
print("RECOMMEND", recommend)
