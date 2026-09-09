-- Template: VWAP per stock_code × date (default stock only).
-- Access A: add AND stock_code = ?
-- Access B: add AND date = ?
SELECT
  stock_code,
  date,
  SUM(Volume * Price) / NULLIF(SUM(Volume), 0) AS vwap,
  SUM(Volume) AS volume,
  COUNT(*) AS ticks
FROM l2_main
WHERE instrument_type = 'stock'
  AND session LIKE 'continuous%'
GROUP BY stock_code, date
