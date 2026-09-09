-- Template: tick speed (ticks / volume / notional per minute bucket).
-- Access D: time-slice via extra_where on Time/session.
SELECT
  stock_code,
  date,
  SUBSTRING(Time, 1, 5) AS minute_bucket,
  COUNT(*) AS ticks,
  SUM(Volume) AS volume,
  SUM(Volume * Price) AS notional
FROM l2_main
WHERE instrument_type = 'stock'
  AND session LIKE 'continuous%'
GROUP BY stock_code, date, minute_bucket
