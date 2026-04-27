from sqlalchemy import Boolean, CheckConstraint, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.adapters.driven import Base


class SettingsModel(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str] = mapped_column(String(50), default="")
    email: Mapped[str] = mapped_column(String(100), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    working_hours: Mapped[str] = mapped_column(String(50), default="")
    coords_lat: Mapped[float] = mapped_column(Float, default=0.0)
    coords_lon: Mapped[float] = mapped_column(Float, default=0.0)
    instagram: Mapped[str] = mapped_column(String(255), default="")
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
    __table_args__ = (CheckConstraint("id = 1", name="single_settings_row"),)
