-- Reusable views. Business definition (document this in every real project):
--   "Valid" order = status IN ('Delivered','Shipped')   -> counts as revenue
--   Cancelled and Returned orders are NOT revenue.
--   revenue = quantity * unit_price ; cogs = quantity * cost_price ; gross profit = revenue - cogs

DROP VIEW IF EXISTS v_lines;
DROP VIEW IF EXISTS v_valid_lines;

CREATE VIEW v_lines AS
SELECT
    o.order_id,
    o.customer_id,
    o.order_date,
    strftime('%Y-%m', o.order_date) AS order_month,
    o.status,
    o.payment_method,
    o.delivery_days,
    o.coupon_used,
    c.city, c.region, c.acquisition_channel, c.age_group, c.gender,
    i.product_id, p.product_name, p.category, p.sub_category,
    i.quantity, i.unit_price, i.discount_pct,
    i.quantity * i.unit_price AS revenue,
    i.quantity * p.cost_price AS cogs
FROM order_items i
JOIN orders    o ON o.order_id   = i.order_id
JOIN products  p ON p.product_id = i.product_id
JOIN customers c ON c.customer_id = o.customer_id;

CREATE VIEW v_valid_lines AS
SELECT * FROM v_lines WHERE status IN ('Delivered', 'Shipped');
