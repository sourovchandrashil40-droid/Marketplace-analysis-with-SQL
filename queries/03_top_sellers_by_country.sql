-- 03 | Top 3 sellers per country and how much of the country's GMV they hold
-- Question: Who are the power sellers in each market, and how dependent is each market on them?
-- Techniques: multi-step CTEs, RANK() OVER (PARTITION BY ...), SUM() OVER (PARTITION BY ...)

WITH seller_gmv AS (
    SELECT
        u.country,
        i.seller_id,
        COUNT(*)                  AS orders,
        ROUND(SUM(o.sale_price), 2) AS gmv
    FROM orders o
    JOIN items  i ON i.item_id = o.item_id
    JOIN users  u ON u.user_id = i.seller_id
    WHERE o.status = 'completed'
    GROUP BY u.country, i.seller_id
),
ranked AS (
    SELECT
        country,
        seller_id,
        orders,
        gmv,
        RANK()    OVER (PARTITION BY country ORDER BY gmv DESC) AS rank_in_country,
        SUM(gmv)  OVER (PARTITION BY country)                   AS country_gmv
    FROM seller_gmv
)
SELECT
    country,
    rank_in_country,
    seller_id,
    orders,
    gmv,
    ROUND(100.0 * gmv / country_gmv, 1) AS pct_of_country_gmv
FROM ranked
WHERE rank_in_country <= 3
ORDER BY country, rank_in_country;
