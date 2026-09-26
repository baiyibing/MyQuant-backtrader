from pathlib import Path
p = Path(r"backtest_output/joint-return-v1-modeb-bars-format-bench/artifacts/subset_bars.json")
raw = open(p, "rb").read(2000)
print("size", p.stat().st_size)
print("head_ascii", raw[:300].decode("ascii", "replace"))
print("has_content_sha256", b"content_sha256" in raw)
print("has_metadata", b"metadata" in raw)
print("starts_with", raw[:20])
# check end for seal
end = open(p, "rb")
end.seek(max(0, p.stat().st_size - 500))
tail = end.read()
print("tail_ascii", tail.decode("ascii", "replace"))
