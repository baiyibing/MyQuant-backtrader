-- Template: VWAP with front-adjusted prices (Price * cumulative_adj_factor).
-- Requires l2_adj_factor (registered from stock_data/adj_factor.parquet).
-- Rows without a factor keep price_adj NULL and are excluded from vwap_adj.
SELECT
  m.stock_code,
  m.date,
  SUM(m.Volume * m.Price) / NULLIF(SUM(m.Volume), 0) AS vwap_raw,
  SUM(m.Volume * m.Price * a.cumulative_adj_factor)
    / NULLIF(SUM(CASE WHEN a.cumulative_adj_factor IS NOT NULL THEN m.Volume ELSE 0 END), 0)
    AS vwap_adj,
  SUM(m.Volume) AS volume,
  COUNT(*) AS ticks
FROM l2_main m
LEFT JOIN l2_adj_factor a
  ON m.stock_code = a.stock_code AND m.date = a.date
WHERE m.instrument_type = 'stock'
  AND m.session LIKE 'continuous%'
GROUP BY m.stock_code, m.date
