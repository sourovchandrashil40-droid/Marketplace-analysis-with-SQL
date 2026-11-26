-- 01 | Monthly GMV, orders and average order value, with month-over-month growth
-- Question: How fast is the marketplace growing, and is growth steady or seasonal?
-- Techniques: CTE, GROUP BY, LAG(), moving average window frame
-- Note: only completed orders count towards GMV (cancelled/refunded are excluded).

WITH monthly AS (
    SELECT
        strftime('%Y-%m', order_date) AS month,
        COUNT(*)                      AS orders,
        ROUND(SUM(sale_price), 2)     AS gmv,
        ROUND(AVG(sale_price), 2)     AS aov
    FROM orders
    WHERE status = 'completed'
    GROUP BY 1
)
SELECT
    month,
    orders,
    gmv,
    aov,
    ROUND(100.0 * (gmv - LAG(gmv) OVER (ORDER BY month))
                / LAG(gmv) OVER (ORDER BY month), 1)                     AS gmv_mom_pct,
    ROUND(AVG(gmv) OVER (ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS gmv_3m_avg
FROM monthly
ORDER BY month;
