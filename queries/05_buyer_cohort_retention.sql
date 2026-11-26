-- 05 | Buyer cohort retention (monthly)
-- Question: Of the buyers who made their first purchase in month X, what share
--           buys again 1, 2, ... 6 months later?
-- Techniques: chained CTEs, date arithmetic, self-referencing cohort size, DISTINCT counts
-- Output is long format (one row per cohort x months_since); the Python runner pivots it.
-- Excluded: cohorts whose 6-month follow-up window is cut off by the end of the data,
-- and cohorts with fewer than 30 buyers (percentages on tiny groups are just noise).

WITH purchase_months AS (               -- one row per buyer per active month
    SELECT DISTINCT
        buyer_id,
        strftime('%Y-%m', order_date) AS order_month
    FROM orders
    WHERE status = 'completed'
),
first_purchase AS (
    SELECT buyer_id, MIN(order_month) AS cohort_month
    FROM purchase_months
    GROUP BY buyer_id
),
activity AS (
    SELECT
        f.cohort_month,
        (CAST(substr(p.order_month, 1, 4) AS INTEGER) - CAST(substr(f.cohort_month, 1, 4) AS INTEGER)) * 12
      + (CAST(substr(p.order_month, 6, 2) AS INTEGER) - CAST(substr(f.cohort_month, 6, 2) AS INTEGER))
                                       AS months_since,
        COUNT(DISTINCT p.buyer_id)     AS active_buyers
    FROM purchase_months p
    JOIN first_purchase  f USING (buyer_id)
    GROUP BY f.cohort_month, months_since
),
cohort_size AS (
    SELECT cohort_month, active_buyers AS cohort_buyers
    FROM activity
    WHERE months_since = 0
)
SELECT
    a.cohort_month,
    c.cohort_buyers,
    a.months_since,
    a.active_buyers,
    ROUND(100.0 * a.active_buyers / c.cohort_buyers, 1) AS retention_pct
FROM activity a
JOIN cohort_size c USING (cohort_month)
WHERE a.months_since BETWEEN 0 AND 6
  AND a.cohort_month <= '2026-04'      -- cohorts with a full 6-month window before 2026-10
  AND c.cohort_buyers >= 30
ORDER BY a.cohort_month, a.months_since;
