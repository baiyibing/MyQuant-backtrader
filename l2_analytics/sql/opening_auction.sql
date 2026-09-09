-- Template: opening (pre_open) vs continuous auction comparison per stock_code x date.
SELECT
  stock_code,
  date,
  SUM(CASE WHEN session = 'pre_open' THEN 1 ELSE 0 END) AS auction_ticks,
  SUM(CASE WHEN session = 'pre_open' THEN Volume ELSE 0 END) AS auction_volume,
  SUM(CASE WHEN session = 'pre_open' THEN Volume * Price ELSE 0 END) AS auction_notional,
  SUM(CASE WHEN session LIKE 'continuous%' THEN 1 ELSE 0 END) AS continuous_ticks,
  SUM(CASE WHEN session LIKE 'continuous%' THEN Volume ELSE 0 END) AS continuous_volume,
  SUM(CASE WHEN session LIKE 'continuous%' THEN Volume * Price ELSE 0 END) AS continuous_notional
FROM l2_main
WHERE instrument_type = 'stock'
GROUP BY stock_code, date
