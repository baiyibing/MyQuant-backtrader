-- Template: 主买卖净流入 (本数据约定口径: Type=B 主动买).
-- NOT comparable to Eastmoney/THS without external calibration.
-- Default: continuous auction only (pre_open/close_auction B/S ambiguous).
SELECT
  stock_code,
  date,
  SUM(CASE WHEN Type = 'B' THEN Volume * Price ELSE -Volume * Price END) AS net_inflow,
  SUM(CASE WHEN Type = 'B' THEN Volume * Price ELSE 0 END) AS buy_notional,
  SUM(CASE WHEN Type = 'S' THEN Volume * Price ELSE 0 END) AS sell_notional,
  COUNT(*) AS ticks
FROM l2_main
WHERE instrument_type = 'stock'
  AND session LIKE 'continuous%'
GROUP BY stock_code, date
