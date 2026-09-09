-- Template: price impact of large trades (5-tick forward displacement).
-- Large trade = Volume * Price >= 1,000,000 (notional threshold).
-- r5 🔴-1 FIX: LEAD must run on the FULL tick stream BEFORE filtering to large
-- trades — otherwise LEAD(Price,5) gives "5 large trades later" not "5 ticks later"
-- (silent wrong). CTE computes LEAD on full continuous-stock stream, outer query
-- filters to large trades.
-- Window function (no GROUP BY); Access A: add AND stock_code = ? AND date = ?
WITH tick_stream AS (
  SELECT
    stock_code, date, TranID, Time, Price, Volume, Type,
    Volume * Price AS trade_notional,
    LEAD(Price, 5) OVER (PARTITION BY stock_code, date ORDER BY TranID) AS price_5t_later
  FROM l2_main
  WHERE instrument_type = 'stock'
    AND session LIKE 'continuous%'
)
SELECT
  stock_code,
  date,
  TranID,
  Time,
  Price,
  Volume,
  trade_notional,
  Type,
  price_5t_later,
  price_5t_later - Price AS impact_5t
FROM tick_stream
WHERE trade_notional >= 1000000
