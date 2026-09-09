-- Template: 买方拆单聚簇 via BuyOrderID (mirror of SaleOrderID / sell-side).
-- Must GROUP BY stock_code, date, BuyOrderID (OrderID reused across symbols/days).
-- Join order side; HAVING fill_count >= 5 OR notional >= 1e6 (same thresholds as sell).
SELECT
  o.stock_code,
  o.date,
  o.BuyOrderID,
  COUNT(*) AS fill_count,
  SUM(m.Volume) AS total_volume,
  SUM(m.Volume * m.Price) AS total_notional,
  MIN(m.TranID) AS first_tran_id,
  MAX(m.TranID) AS last_tran_id
FROM l2_order o
INNER JOIN l2_main m
  ON o.stock_code = m.stock_code
 AND o.date = m.date
 AND o.TranID = m.TranID
WHERE m.instrument_type = 'stock'
  AND m.session LIKE 'continuous%'
GROUP BY o.stock_code, o.date, o.BuyOrderID
HAVING COUNT(*) >= 5
    OR SUM(m.Volume * m.Price) >= 1000000
