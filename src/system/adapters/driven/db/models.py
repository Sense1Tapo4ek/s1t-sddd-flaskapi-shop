from sqlalchemy import Boolean, CheckConstraint, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.adapters.driven import Base
from shared.adapters.driven.db.base import mysql_table_opts


class SettingsModel(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str] = mapped_column(String(50), default="")
    email: Mapped[str] = mapped_column(String(100), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    working_hours_schedule: Mapped[str] = mapped_column(Text, default="", nullable=False)
    coords_lat: Mapped[float] = mapped_column(Float, default=0.0)
    coords_lon: Mapped[float] = mapped_column(Float, default=0.0)
    instagram: Mapped[str] = mapped_column(String(255), default="")
    telegram_public_url: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    whatsapp_url: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    viber_url: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    telegram_bot_token: Mapped[str] = mapped_column(String(255), default="")
    telegram_chat_id: Mapped[str] = mapped_column(String(100), default="")
    app_name: Mapped[str] = mapped_column(String(100), default="Shop Admin", nullable=False)
    admin_panel_title: Mapped[str] = mapped_column(String(100), default="Админ панель", nullable=False)
    owner_can_view_category_tree: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    owner_can_edit_taxonomy: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    owner_can_view_products: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    owner_can_edit_products: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    owner_can_create_demo_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Singleton enforcement
    __table_args__ = (
        CheckConstraint("id = 1", name="single_settings_row"),
        mysql_table_opts(),
    )


class StorageSettingsModel(Base):
    __tablename__ = "storage_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    backend: Mapped[str] = mapped_column(String(16), default="local", nullable=False)
    endpoint_url: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    region: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    bucket: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    access_key_id: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    # Encrypted Fernet token (URL-safe base64). Empty when not set.
    secret_access_key_enc: Mapped[str] = mapped_column(Text, default="", nullable=False)
    public_base_url: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    force_path_style: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        CheckConstraint("id = 1", name="single_storage_settings_row"),
        mysql_table_opts(),
    )
