-- Template: 卖方拆单聚簇 via SaleOrderID (must GROUP BY stock_code, date, SaleOrderID).
-- Buy-side mirror: buy_order_cluster.sql (BuyOrderID).
-- Join order side; filter clusters with >= :min_fills fills or notional >= :min_notional.
--
-- PERF: full-market (mode C) ad-hoc join+groupby is minutes (~185–270s/day). Prefer
-- ``large_order_cluster_agg`` over persisted ``l2_cluster_agg`` (build once via
-- ``run_l2_build_aggregates.py``). Keep this template for single-stock / ad-hoc.
SELECT
  o.stock_code,
  o.date,
  o.SaleOrderID,
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
GROUP BY o.stock_code, o.date, o.SaleOrderID
HAVING COUNT(*) >= 5
    OR SUM(m.Volume * m.Price) >= 1000000
