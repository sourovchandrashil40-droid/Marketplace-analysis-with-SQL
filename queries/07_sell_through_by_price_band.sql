-- 07 | 30-day sell-through rate by price band
-- Question: How does list price affect the chance an item sells within 30 days?
-- Techniques: subquery, CASE bucketing, LEFT JOIN with a time-window condition
-- Only items listed at least 30 days before the end of the data are included, so
-- every item has had the full window to sell (avoids right-censoring bias).

SELECT
    price_band,
    COUNT(*)                                       AS items_listed,
    SUM(sold_30d)                                  AS sold_within_30d,
    ROUND(100.0 * SUM(sold_30d) / COUNT(*), 1)     AS sell_through_30d_pct
FROM (
    SELECT
        i.item_id,
        CASE
            WHEN i.list_price < 10 THEN '1) under 10'
            WHEN i.list_price < 25 THEN '2) 10-24.99'
            WHEN i.list_price < 50 THEN '3) 25-49.99'
            ELSE                        '4) 50+'
        END AS price_band,
        CASE WHEN o.order_id IS NOT NULL THEN 1 ELSE 0 END AS sold_30d
    FROM items i
    LEFT JOIN orders o
           ON o.item_id = i.item_id
          AND o.status  = 'completed'
          AND julianday(o.order_date) - julianday(i.listed_at) <= 30
    WHERE i.listed_at <= date('2026-10-31', '-30 day')
)
GROUP BY price_band
ORDER BY price_band;
