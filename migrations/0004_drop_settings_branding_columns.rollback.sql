ALTER TABLE settings
    ADD COLUMN app_name VARCHAR(100) NOT NULL DEFAULT 'Shop Admin' AFTER telegram_chat_id,
    ADD COLUMN admin_panel_title VARCHAR(100) NOT NULL DEFAULT 'Админ панель' AFTER app_name;
