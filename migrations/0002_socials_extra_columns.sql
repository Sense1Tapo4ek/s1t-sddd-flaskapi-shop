-- Add three new optional social-network columns to site_settings.
-- Each column is gated at runtime by a SystemConfig.socials_*_enabled
-- flag (see docs/subsystems/feature-flags.md). The columns exist
-- unconditionally so that flipping a flag back to True re-exposes the
-- previously stored value without further DDL.

ALTER TABLE settings
    ADD COLUMN telegram_public_url VARCHAR(255) NOT NULL DEFAULT '' AFTER instagram,
    ADD COLUMN whatsapp_url        VARCHAR(255) NOT NULL DEFAULT '' AFTER telegram_public_url,
    ADD COLUMN viber_url           VARCHAR(255) NOT NULL DEFAULT '' AFTER whatsapp_url;
