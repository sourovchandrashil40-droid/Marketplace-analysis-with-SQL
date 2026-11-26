-- 06 | Acquisition channel quality: signup -> first purchase conversion
-- Question: Which acquisition channels bring users who actually buy?
-- Techniques: LEFT JOIN to keep non-buyers, conditional aggregation, date difference
-- Only users who signed up at least 30 days before the end of the data are included,
-- so every user has had the full 30-day window to convert (avoids right-censoring bias).

WITH first_order AS (
    SELECT
        buyer_id,
        MIN(order_date) AS first_order_date
    FROM orders
    WHERE status = 'completed'
    GROUP BY buyer_id
)
SELECT
    u.acquisition_channel,
    COUNT(*)                                                           AS users,
    SUM(CASE WHEN julianday(f.first_order_date) - julianday(u.signup_date) <= 30
             THEN 1 ELSE 0 END)                                        AS buyers_within_30d,
    ROUND(100.0 * SUM(CASE WHEN julianday(f.first_order_date) - julianday(u.signup_date) <= 30
                           THEN 1 ELSE 0 END) / COUNT(*), 1)           AS conversion_30d_pct,
    ROUND(100.0 * SUM(CASE WHEN f.buyer_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1)
                                                                       AS ever_bought_pct
FROM users u
LEFT JOIN first_order f ON f.buyer_id = u.user_id
WHERE u.signup_date <= date('2026-10-31', '-30 day')
GROUP BY u.acquisition_channel
ORDER BY conversion_30d_pct DESC;
