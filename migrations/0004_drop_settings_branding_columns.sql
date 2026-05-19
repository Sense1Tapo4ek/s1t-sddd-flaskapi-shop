-- Drop the in-DB branding fields.
-- ``app_name`` and ``admin_panel_title`` are now env-only
-- (ROOT_APP_NAME, ROOT_ADMIN_PANEL_TITLE). The admin form no longer
-- exposes them; the runtime context reads from RootConfig.

ALTER TABLE settings
    DROP COLUMN app_name,
    DROP COLUMN admin_panel_title;
