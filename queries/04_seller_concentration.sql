-- 04 | Seller concentration: GMV share by seller decile
-- Question: How concentrated is supply? Do a few sellers generate most of the GMV?
-- Techniques: NTILE(), cumulative SUM() window, nested aggregation
-- Decile 1 = the top 10% of selling sellers (sellers with at least one completed sale).

WITH seller_gmv AS (
    SELECT
        i.seller_id,
        SUM(o.sale_price) AS gmv
    FROM orders o
    JOIN items  i ON i.item_id = o.item_id
    WHERE o.status = 'completed'
    GROUP BY i.seller_id
),
bucketed AS (
    SELECT
        seller_id,
        gmv,
        NTILE(10) OVER (ORDER BY gmv DESC) AS decile
    FROM seller_gmv
),
by_decile AS (
    SELECT
        decile,
        COUNT(*)        AS sellers,
        SUM(gmv)        AS gmv
    FROM bucketed
    GROUP BY decile
)
SELECT
    decile,
    sellers,
    ROUND(gmv, 2)                                                    AS gmv,
    ROUND(100.0 * gmv / SUM(gmv) OVER (), 1)                         AS gmv_share_pct,
    ROUND(100.0 * SUM(gmv) OVER (ORDER BY decile)
                / SUM(gmv) OVER (), 1)                               AS cumulative_share_pct
FROM by_decile
ORDER BY decile;
