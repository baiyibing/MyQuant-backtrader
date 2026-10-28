# Phase3 watermark-tolerant CSV read

Base: `f8d21de1ef6c0321f111920188c61b617f6ba800` (#520).

Human probe on newtest_4090 reports GBK vendor CSVs from 2022-02-24 onward
with a twelfth `原创:cfht.taobao.com(QQ:515005403)` header field and occasional
matching body fields. Fixed eleven-column reads reject those rows; UTF-8
reads reject the GBK watermark bytes.

Both gap-free validation and chunk ETL now share a fixed eleven-column reader
with `auto_detect=false` and `strict_mode=false`. Files whose headers do not
decode as UTF-8 use `encoding='latin-1'`; UTF-8 headers retain UTF-8 reading.
This small grouping is necessary because local DuckDB 1.5.6 rejects existing
UTF-8 Chinese header fixtures when forced through its latin-1 decoder. Mixed
encoding chunks use UNION ALL and retain their filename attribution.

Regression coverage uses actual GBK watermark bytes, mixed eleven/twelve-field
rows and a UTF-8 companion file. It checks B/S row retention and main/order
values, plus contiguous and gapped TranIDs under full/sample validation.
The new fixture reproduced the column-count error before the change.

This is synthetic verification, not a rerun of the affected host days.
Phase3 remains stopped; no lake/CSV cleanup or restart is part of this change.
No skip dates were added; skip lists remain for truly unrecoverable days.
Grok is skipped per Human instruction; Claude review is left to others.
