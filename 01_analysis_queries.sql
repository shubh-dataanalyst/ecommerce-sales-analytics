-- name: kpi_overview
SELECT ROUND(SUM(revenue))                                   AS revenue,
       COUNT(DISTINCT order_id)                              AS orders,
       COUNT(DISTINCT customer_id)                           AS customers,
       ROUND(SUM(revenue) / COUNT(DISTINCT order_id))        AS aov,
       ROUND(SUM(revenue - cogs))                            AS gross_profit,
       ROUND(100.0 * SUM(revenue - cogs) / SUM(revenue), 1)  AS margin_pct
FROM v_valid_lines;

-- name: order_status_mix
SELECT status,
       COUNT(*) AS orders,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM orders
GROUP BY status
ORDER BY orders DESC;

-- name: monthly_trend
WITH m AS (
    SELECT order_month,
           SUM(revenue)             AS revenue,
           COUNT(DISTINCT order_id) AS orders,
           SUM(revenue - cogs)      AS gross_profit
    FROM v_valid_lines
    GROUP BY order_month
)
SELECT order_month,
       ROUND(revenue)       AS revenue,
       orders,
       ROUND(gross_profit)  AS gross_profit,
       ROUND(100.0 * gross_profit / revenue, 1) AS margin_pct,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY order_month))
             / LAG(revenue) OVER (ORDER BY order_month), 1) AS mom_growth_pct
FROM m
ORDER BY order_month;

-- name: category_profitability
SELECT category,
       ROUND(SUM(revenue))                                  AS revenue,
       ROUND(SUM(revenue - cogs))                           AS gross_profit,
       ROUND(100.0 * SUM(revenue - cogs) / SUM(revenue), 1) AS margin_pct,
       SUM(quantity)                                        AS units,
       ROUND(100.0 * SUM(revenue) / SUM(SUM(revenue)) OVER (), 1) AS revenue_share_pct
FROM v_valid_lines
GROUP BY category
ORDER BY revenue DESC;

-- name: top10_products
SELECT product_id, product_name, category,
       ROUND(SUM(revenue))                                  AS revenue,
       SUM(quantity)                                        AS units,
       ROUND(100.0 * SUM(revenue - cogs) / SUM(revenue), 1) AS margin_pct,
       RANK() OVER (ORDER BY SUM(revenue) DESC)             AS revenue_rank
FROM v_valid_lines
GROUP BY product_id, product_name, category
ORDER BY revenue_rank
LIMIT 10;

-- name: region_performance
SELECT region,
       COUNT(DISTINCT customer_id)                            AS customers,
       COUNT(DISTINCT order_id)                               AS orders,
       ROUND(SUM(revenue))                                    AS revenue,
       ROUND(SUM(revenue) / COUNT(DISTINCT order_id))         AS aov,
       ROUND(SUM(revenue) / COUNT(DISTINCT customer_id))      AS revenue_per_customer
FROM v_valid_lines
GROUP BY region
ORDER BY revenue DESC;

-- name: city_performance
SELECT city, region,
       COUNT(DISTINCT customer_id) AS customers,
       ROUND(SUM(revenue))         AS revenue
FROM v_valid_lines
GROUP BY city, region
ORDER BY revenue DESC;

-- name: channel_performance
SELECT c.acquisition_channel,
       COUNT(DISTINCT c.customer_id)                                              AS customers_acquired,
       COUNT(DISTINCT l.customer_id)                                              AS buyers,
       ROUND(100.0 * COUNT(DISTINCT l.customer_id) / COUNT(DISTINCT c.customer_id), 1) AS conversion_pct,
       ROUND(COALESCE(SUM(l.revenue), 0))                                         AS revenue,
       ROUND(COALESCE(SUM(l.revenue), 0) / COUNT(DISTINCT c.customer_id))         AS revenue_per_acquired_customer
FROM customers c
LEFT JOIN v_valid_lines l ON l.customer_id = c.customer_id
GROUP BY c.acquisition_channel
ORDER BY revenue DESC;

-- name: payment_method_risk
SELECT payment_method,
       COUNT(*)                                                    AS orders,
       ROUND(100.0 * SUM(status = 'Cancelled') / COUNT(*), 1)      AS cancel_pct,
       ROUND(100.0 * SUM(status = 'Returned')  / COUNT(*), 1)      AS return_pct
FROM orders
GROUP BY payment_method
ORDER BY cancel_pct DESC;

-- name: repeat_purchase
WITH oc AS (
    SELECT customer_id, COUNT(DISTINCT order_id) AS n_orders
    FROM v_valid_lines
    GROUP BY customer_id
)
SELECT COUNT(*)                                   AS buyers,
       SUM(n_orders > 1)                          AS repeat_buyers,
       ROUND(100.0 * SUM(n_orders > 1) / COUNT(*), 1) AS repeat_rate_pct,
       ROUND(AVG(n_orders), 2)                    AS avg_orders_per_buyer
FROM oc;

-- name: pareto_deciles
WITH cr AS (
    SELECT customer_id, SUM(revenue) AS rev
    FROM v_valid_lines
    GROUP BY customer_id
), d AS (
    SELECT customer_id, rev, NTILE(10) OVER (ORDER BY rev DESC) AS decile
    FROM cr
)
SELECT decile,
       COUNT(*)                                             AS customers,
       ROUND(SUM(rev))                                      AS revenue,
       ROUND(100.0 * SUM(rev) / SUM(SUM(rev)) OVER (), 1)   AS pct_of_revenue
FROM d
GROUP BY decile
ORDER BY decile;

-- name: discount_bands
SELECT CASE WHEN discount_pct = 0   THEN '1) 0%'
            WHEN discount_pct <= 10 THEN '2) 5-10%'
            WHEN discount_pct <= 20 THEN '3) 15-20%'
            WHEN discount_pct <= 30 THEN '4) 25-30%'
            ELSE                         '5) 35%+' END           AS discount_band,
       COUNT(*)                                                   AS lines,
       SUM(quantity)                                              AS units,
       ROUND(SUM(revenue))                                        AS revenue,
       ROUND(100.0 * SUM(revenue - cogs) / SUM(revenue), 1)       AS margin_pct,
       SUM(revenue - cogs < 0)                                    AS loss_making_lines
FROM v_valid_lines
GROUP BY discount_band
ORDER BY discount_band;

-- name: delivery_vs_returns
SELECT CASE WHEN delivery_days <= 3 THEN '1-3 days'
            WHEN delivery_days <= 5 THEN '4-5 days'
            WHEN delivery_days <= 7 THEN '6-7 days'
            ELSE '8+ days' END                                       AS delivery_bucket,
       COUNT(*)                                                      AS orders,
       ROUND(100.0 * SUM(status = 'Returned') / COUNT(*), 1)         AS return_pct
FROM orders
WHERE delivery_days IS NOT NULL AND status IN ('Delivered', 'Returned')
GROUP BY delivery_bucket
ORDER BY MIN(delivery_days);

-- name: cohort_retention
WITH act AS (
    SELECT DISTINCT customer_id, order_month FROM v_valid_lines
), first_m AS (
    SELECT customer_id, MIN(order_month) AS cohort FROM act GROUP BY customer_id
), joined AS (
    SELECT f.cohort,
           (CAST(substr(a.order_month, 1, 4) AS INT) * 12 + CAST(substr(a.order_month, 6, 2) AS INT))
         - (CAST(substr(f.cohort, 1, 4) AS INT) * 12 + CAST(substr(f.cohort, 6, 2) AS INT)) AS month_n,
           a.customer_id
    FROM act a JOIN first_m f USING (customer_id)
)
SELECT cohort, month_n, COUNT(DISTINCT customer_id) AS active_customers
FROM joined
GROUP BY cohort, month_n
ORDER BY cohort, month_n;
