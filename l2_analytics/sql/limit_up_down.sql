-- Template: INTRADAY EXTREME PRICE CONCENTRATION (proxy, NOT true limit-up/down).
-- r5 🟡-1: This uses MAX/MIN(Price) which every stock-day has → zero filtering power
-- for real limit-up/down detection. True limit-up → template ``limit_up_down_true``
-- (prev_close × board%; v5.9). This file remains a price-concentration exploratory proxy.
-- ticks_at_high / ticks_at_low ratio indicates how clustered ticks are at day extremes.
WITH extremes AS (
  SELECT stock_code, date, MAX(Price) AS day_high, MIN(Price) AS day_low
  FROM l2_main
  WHERE instrument_type = 'stock' AND session LIKE 'continuous%'
  GROUP BY stock_code, date
)
SELECT
  m.stock_code,
  m.date,
  e.day_high,
  e.day_low,
  COUNT(*) AS ticks,
  SUM(CASE WHEN m.Price = e.day_high THEN 1 ELSE 0 END) AS ticks_at_high,
  SUM(CASE WHEN m.Price = e.day_low THEN 1 ELSE 0 END) AS ticks_at_low,
  SUM(CASE WHEN m.Type = 'B' AND m.Price = e.day_high THEN m.Volume ELSE 0 END) AS buy_vol_at_high,
  SUM(CASE WHEN m.Type = 'S' AND m.Price = e.day_low THEN m.Volume ELSE 0 END) AS sell_vol_at_low
FROM l2_main m
INNER JOIN extremes e ON m.stock_code = e.stock_code AND m.date = e.date
WHERE m.instrument_type = 'stock'
  AND m.session LIKE 'continuous%'
GROUP BY m.stock_code, m.date, e.day_high, e.day_low
