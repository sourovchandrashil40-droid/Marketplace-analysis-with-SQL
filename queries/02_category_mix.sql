-- 02 | Category performance: GMV share, basket size and discount depth
-- Question: Which categories drive revenue, and how much do buyers negotiate?
-- Techniques: JOIN, aggregate over a window (share of total), ratio metrics

SELECT
    i.category,
    COUNT(*)                                                       AS orders,
    ROUND(SUM(o.sale_price), 2)                                    AS gmv,
    ROUND(100.0 * SUM(o.sale_price) / SUM(SUM(o.sale_price)) OVER (), 1) AS gmv_share_pct,
    ROUND(100.0 * COUNT(*)          / SUM(COUNT(*))          OVER (), 1) AS order_share_pct,
    ROUND(AVG(o.sale_price), 2)                                    AS aov,
    ROUND(100.0 * (1 - SUM(o.sale_price) / SUM(i.list_price)), 1)  AS avg_discount_pct
FROM orders o
JOIN items  i ON i.item_id = o.item_id
WHERE o.status = 'completed'
GROUP BY i.category
ORDER BY gmv DESC;
