-- Rollback for 0001_init. Drop in reverse FK order.
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS product_images;
DROP TABLE IF EXISTS product_attribute_values;
DROP TABLE IF EXISTS attribute_options;
DROP TABLE IF EXISTS category_attributes;
DROP TABLE IF EXISTS product_tags;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS tags;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS storage_settings;
DROP TABLE IF EXISTS settings;
DROP TABLE IF EXISTS admins;
SET FOREIGN_KEY_CHECKS = 1;
