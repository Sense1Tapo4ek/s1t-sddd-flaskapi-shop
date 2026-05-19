-- Snapshot the customer contacts on the order itself.
-- `contact_email` mirrors what was placed at order time (customer may
-- change profile email later); `contact_phone` is captured at placement
-- and is required at the wire layer but stays NULLABLE here for
-- backfill of legacy rows.

ALTER TABLE orders
    ADD COLUMN contact_email VARCHAR(255) NOT NULL DEFAULT '' AFTER customer_user_id,
    ADD COLUMN contact_phone VARCHAR(50)  NOT NULL DEFAULT '' AFTER contact_email;
