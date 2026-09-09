-- Template: tick/volume distribution across trading sessions per stock_code x date.
-- Compares pre_open / continuous_am / continuous_pm / close_auction / other activity.
SELECT
  stock_code,
  date,
  session,
  COUNT(*) AS ticks,
  SUM(Volume) AS volume,
  SUM(Volume * Price) AS notional,
  SUM(CASE WHEN Type = 'B' THEN Volume ELSE 0 END) AS buy_volume,
  SUM(CASE WHEN Type = 'S' THEN Volume ELSE 0 END) AS sell_volume
FROM l2_main
WHERE instrument_type = 'stock'
GROUP BY stock_code, date, session
