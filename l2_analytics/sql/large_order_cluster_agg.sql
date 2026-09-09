-- Template: 卖方拆单聚簇 — FAST path over persisted ``l2_cluster_agg``.
-- Same HAVING thresholds as ``large_order_cluster.sql`` / ``aggregates.CLUSTER_AGG_SQL``.
-- Use this for mode-C full-market scans (seconds). Rebuild agg via
-- ``scripts/run/run_l2_build_aggregates.py`` after ETL; raw join+groupby stays
-- in ``large_order_cluster.sql`` for ad-hoc / single-stock exploration.
SELECT
  stock_code,
  date,
  SaleOrderID,
  fill_count,
  total_volume,
  total_notional,
  first_tran_id,
  last_tran_id
FROM l2_cluster_agg
WHERE 1 = 1
