-- 0001 — Initial schema.
-- Derived from src/<context>/adapters/driven/db/models.py at the time of the
-- MySQL switch. Reflects the union of all tables previously created by
-- Base.metadata.create_all + ensure_sqlite_compatibility patches.

CREATE TABLE admins (
    id INT NOT NULL AUTO_INCREMENT,
    login VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(30) NOT NULL DEFAULT 'owner',
    telegram_chat_id VARCHAR(100) NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    password_changed_at DATETIME NULL,
    recovery_code_hash VARCHAR(255) NULL,
    recovery_code_expires DATETIME NULL,
    recovery_code_attempts INT NOT NULL DEFAULT 0,
    recovery_code_last_sent_at DATETIME NULL,
    recovery_code_locked_until DATETIME NULL,
    token_version INT NOT NULL DEFAULT 0,
    last_login_at DATETIME NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_admins_login (login)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE customers (
    id INT NOT NULL AUTO_INCREMENT,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    token_version INT NOT NULL DEFAULT 0,
    last_login_at DATETIME NULL,
    recovery_code_hash VARCHAR(255) NULL,
    recovery_code_expires DATETIME NULL,
    recovery_code_attempts INT NOT NULL DEFAULT 0,
    recovery_code_last_sent_at DATETIME NULL,
    recovery_code_locked_until DATETIME NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_customers_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE settings (
    id INT NOT NULL,
    phone VARCHAR(50) NOT NULL DEFAULT '',
    email VARCHAR(100) NOT NULL DEFAULT '',
    address TEXT NOT NULL,
    working_hours VARCHAR(50) NOT NULL DEFAULT '',
    coords_lat FLOAT NOT NULL DEFAULT 0,
    coords_lon FLOAT NOT NULL DEFAULT 0,
    instagram VARCHAR(255) NOT NULL DEFAULT '',
    telegram_bot_token VARCHAR(255) NOT NULL DEFAULT '',
    telegram_chat_id VARCHAR(100) NOT NULL DEFAULT '',
    app_name VARCHAR(100) NOT NULL DEFAULT 'Shop Admin',
    admin_panel_title VARCHAR(100) NOT NULL DEFAULT 'Админ панель',
    owner_can_view_category_tree TINYINT(1) NOT NULL DEFAULT 1,
    owner_can_edit_taxonomy TINYINT(1) NOT NULL DEFAULT 0,
    owner_can_view_products TINYINT(1) NOT NULL DEFAULT 0,
    owner_can_edit_products TINYINT(1) NOT NULL DEFAULT 0,
    owner_can_create_demo_data TINYINT(1) NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    CONSTRAINT single_settings_row CHECK (id = 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE storage_settings (
    id INT NOT NULL,
    backend VARCHAR(16) NOT NULL DEFAULT 'local',
    endpoint_url VARCHAR(255) NOT NULL DEFAULT '',
    region VARCHAR(64) NOT NULL DEFAULT '',
    bucket VARCHAR(128) NOT NULL DEFAULT '',
    access_key_id VARCHAR(128) NOT NULL DEFAULT '',
    secret_access_key_enc TEXT NOT NULL,
    public_base_url VARCHAR(255) NOT NULL DEFAULT '',
    force_path_style TINYINT(1) NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    CONSTRAINT single_storage_settings_row CHECK (id = 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE categories (
    id INT NOT NULL AUTO_INCREMENT,
    parent_id INT NULL,
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_categories_slug (slug),
    KEY idx_categories_parent_id (parent_id),
    KEY idx_categories_active_sort (is_active, sort_order),
    CONSTRAINT fk_categories_parent
        FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE tags (
    id INT NOT NULL AUTO_INCREMENT,
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    color VARCHAR(32) NOT NULL DEFAULT '#7c8c6e',
    sort_order INT NOT NULL DEFAULT 0,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_tags_slug (slug),
    KEY idx_tags_active_sort (is_active, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE products (
    id INT NOT NULL AUTO_INCREMENT,
    category_id INT NULL,
    title VARCHAR(255) NOT NULL,
    price FLOAT NOT NULL,
    description TEXT NOT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_products_category_id (category_id),
    KEY idx_products_active_id (is_active, id),
    FULLTEXT KEY ft_products_title_desc (title, description),
    CONSTRAINT fk_products_category
        FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE product_tags (
    product_id INT NOT NULL,
    tag_id INT NOT NULL,
    PRIMARY KEY (product_id, tag_id),
    UNIQUE KEY uq_product_tags_pair (product_id, tag_id),
    KEY idx_product_tags_tag_id (tag_id),
    CONSTRAINT fk_product_tags_product
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    CONSTRAINT fk_product_tags_tag
        FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE category_attributes (
    id INT NOT NULL AUTO_INCREMENT,
    category_id INT NOT NULL,
    code VARCHAR(100) NOT NULL,
    title VARCHAR(255) NOT NULL,
    type VARCHAR(32) NOT NULL,
    unit VARCHAR(50) NULL,
    is_required TINYINT(1) NOT NULL DEFAULT 0,
    is_filterable TINYINT(1) NOT NULL DEFAULT 1,
    is_public TINYINT(1) NOT NULL DEFAULT 1,
    value_mode VARCHAR(16) NOT NULL DEFAULT 'single',
    sort_order INT NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    UNIQUE KEY uq_category_attributes_code (category_id, code),
    KEY idx_category_attributes_category_id (category_id),
    CONSTRAINT fk_category_attributes_category
        FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE attribute_options (
    id INT NOT NULL AUTO_INCREMENT,
    attribute_id INT NOT NULL,
    value VARCHAR(255) NOT NULL,
    label VARCHAR(255) NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    UNIQUE KEY uq_attribute_options_value (attribute_id, value),
    CONSTRAINT fk_attribute_options_attribute
        FOREIGN KEY (attribute_id) REFERENCES category_attributes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE product_attribute_values (
    id INT NOT NULL AUTO_INCREMENT,
    product_id INT NOT NULL,
    attribute_id INT NOT NULL,
    value_text TEXT NULL,
    value_number FLOAT NULL,
    value_bool TINYINT(1) NULL,
    value_json JSON NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_product_attribute_value (product_id, attribute_id),
    KEY idx_product_attribute_values_attribute_id (attribute_id),
    KEY idx_product_attribute_values_text (attribute_id, value_text(64)),
    KEY idx_product_attribute_values_number (attribute_id, value_number),
    KEY idx_product_attribute_values_bool (attribute_id, value_bool),
    CONSTRAINT fk_pav_product
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    CONSTRAINT fk_pav_attribute
        FOREIGN KEY (attribute_id) REFERENCES category_attributes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE product_images (
    id INT NOT NULL AUTO_INCREMENT,
    product_id INT NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    PRIMARY KEY (id),
    KEY idx_product_images_product_id (product_id),
    CONSTRAINT fk_product_images_product
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE inquiries (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(50) NULL,
    contact_email VARCHAR(255) NULL,
    message TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'new',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    author_user_id INT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE orders (
    id INT NOT NULL AUTO_INCREMENT,
    customer_user_id INT NOT NULL,
    total DECIMAL(10,2) NOT NULL,
    delivery_method VARCHAR(20) NOT NULL,
    delivery_address VARCHAR(500) NOT NULL DEFAULT '',
    delivery_comment VARCHAR(500) NOT NULL DEFAULT '',
    comment TEXT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'new',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_orders_customer (customer_user_id),
    KEY idx_orders_status_created (status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE order_items (
    id INT NOT NULL AUTO_INCREMENT,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    title_snapshot VARCHAR(255) NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    quantity INT NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_order_items_order
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
