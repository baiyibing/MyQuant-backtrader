-- Template: TRUE limit-up / limit-down (prev_close × board limit%).
-- Requires l2_prev_close (from adj_factor). Board % only
-- (10%/20%/30%; includes 302). ST 5% not applied (no name feed — data bound).
-- Tick at limit = Price within 0.5 fen of estimated up/down limit.
--
-- Ex-div fix (v5.10): use ``prev_close_d_domain`` =
--   prev_close_none * cum_factor[D-1] / cum_factor[D]
-- so the limit threshold is in D-day raw trading price domain. Falls back to
-- raw ``prev_close`` when factors are missing.
--
-- r6 codex 🟡: tolerance 0.005 (5 厘) covers the rounding boundary ROUND(prev*1.1, 2).
-- Edge case: price exactly between two ticks → rare false positive. Not actionable.
--
-- r6 codex 🟡: l2_prev_close LAG takes previous AVAILABLE trading day (not calendar).
-- Suspension+resumption day → prev_close from last active day, not the gap day.
-- Users should verify on resumption days.
--
-- r6 qoder 🟡-1: board% consolidated to single CTE reference (was 3 inline copies).
WITH day_limits AS (
  SELECT
    p.stock_code,
    p.date,
    COALESCE(p.prev_close_d_domain, p.prev_close) AS prev_close,
    (CASE
      WHEN split_part(p.stock_code, '.', 1) LIKE '300%'
        OR split_part(p.stock_code, '.', 1) LIKE '301%'
        OR split_part(p.stock_code, '.', 1) LIKE '302%' THEN 0.20
      WHEN split_part(p.stock_code, '.', 1) LIKE '688%'
        OR split_part(p.stock_code, '.', 1) LIKE '689%' THEN 0.20
      WHEN split_part(p.stock_code, '.', 1) LIKE '8%'
        OR split_part(p.stock_code, '.', 1) LIKE '4%'
        OR split_part(p.stock_code, '.', 1) LIKE '9%' THEN 0.30
      ELSE 0.10
    END) AS limit_pct
  FROM l2_prev_close p
  WHERE COALESCE(p.prev_close_d_domain, p.prev_close) IS NOT NULL
    AND COALESCE(p.prev_close_d_domain, p.prev_close) > 0
)
SELECT
  m.stock_code,
  m.date,
  d.prev_close,
  d.limit_pct,
  ROUND(d.prev_close * (1 + d.limit_pct), 2) AS up_limit,
  ROUND(d.prev_close * (1 - d.limit_pct), 2) AS down_limit,
  COUNT(*) AS ticks,
  SUM(CASE WHEN abs(m.Price - ROUND(d.prev_close * (1 + d.limit_pct), 2)) < 0.005 THEN 1 ELSE 0 END) AS ticks_at_up,
  SUM(CASE WHEN abs(m.Price - ROUND(d.prev_close * (1 - d.limit_pct), 2)) < 0.005 THEN 1 ELSE 0 END) AS ticks_at_down,
  SUM(CASE WHEN abs(m.Price - ROUND(d.prev_close * (1 + d.limit_pct), 2)) < 0.005 AND m.Type = 'B'
      THEN m.Volume ELSE 0 END) AS buy_vol_at_up,
  SUM(CASE WHEN abs(m.Price - ROUND(d.prev_close * (1 - d.limit_pct), 2)) < 0.005 AND m.Type = 'S'
      THEN m.Volume ELSE 0 END) AS sell_vol_at_down,
  MAX(CASE WHEN abs(m.Price - ROUND(d.prev_close * (1 + d.limit_pct), 2)) < 0.005 THEN 1 ELSE 0 END) AS hit_limit_up,
  MAX(CASE WHEN abs(m.Price - ROUND(d.prev_close * (1 - d.limit_pct), 2)) < 0.005 THEN 1 ELSE 0 END) AS hit_limit_down
FROM l2_main m
INNER JOIN day_limits d ON m.stock_code = d.stock_code AND m.date = d.date
WHERE m.instrument_type = 'stock'
  AND m.session LIKE 'continuous%'
GROUP BY m.stock_code, m.date, d.prev_close, d.limit_pct
HAVING hit_limit_up = 1 OR hit_limit_down = 1
