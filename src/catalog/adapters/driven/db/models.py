from datetime import datetime
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.adapters.driven import Base


class CategoryModel(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_categories_slug"),
        Index("idx_categories_parent_id", "parent_id"),
        Index("idx_categories_active_sort", "is_active", "sort_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    parent: Mapped["CategoryModel | None"] = relationship(
        "CategoryModel", remote_side="CategoryModel.id", back_populates="children"
    )
    children: Mapped[list["CategoryModel"]] = relationship(
        "CategoryModel", back_populates="parent", order_by="CategoryModel.sort_order"
    )
    attributes: Mapped[list["CategoryAttributeModel"]] = relationship(
        "CategoryAttributeModel",
        back_populates="category",
        cascade="all, delete-orphan",
        order_by="CategoryAttributeModel.sort_order",
    )
    products: Mapped[list["ProductModel"]] = relationship(
        "ProductModel", back_populates="category"
    )


class TagModel(Base):
    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_tags_slug"),
        Index("idx_tags_active_sort", "is_active", "sort_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    color: Mapped[str] = mapped_column(String(32), default="#7c8c6e")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    products: Mapped[list["ProductModel"]] = relationship(
        "ProductModel", secondary="product_tags", back_populates="tags"
    )


class ProductTagModel(Base):
    __tablename__ = "product_tags"
    __table_args__ = (
        UniqueConstraint("product_id", "tag_id", name="uq_product_tags_pair"),
        Index("idx_product_tags_tag_id", "tag_id"),
    )

    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )


class CategoryAttributeModel(Base):
    __tablename__ = "category_attributes"
    __table_args__ = (
        UniqueConstraint("category_id", "code", name="uq_category_attributes_code"),
        Index("idx_category_attributes_category_id", "category_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    is_filterable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    value_mode: Mapped[str] = mapped_column(String(16), default="single")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    category: Mapped[CategoryModel] = relationship(
        "CategoryModel", back_populates="attributes"
    )
    options: Mapped[list["AttributeOptionModel"]] = relationship(
        "AttributeOptionModel",
        back_populates="attribute",
        cascade="all, delete-orphan",
        order_by="AttributeOptionModel.sort_order",
    )
    values: Mapped[list["ProductAttributeValueModel"]] = relationship(
        "ProductAttributeValueModel", back_populates="attribute"
    )


class AttributeOptionModel(Base):
    __tablename__ = "attribute_options"
    __table_args__ = (
        UniqueConstraint("attribute_id", "value", name="uq_attribute_options_value"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attribute_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("category_attributes.id", ondelete="CASCADE"), nullable=False
    )
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    attribute: Mapped[CategoryAttributeModel] = relationship(
        "CategoryAttributeModel", back_populates="options"
    )


class ProductModel(Base):
    __tablename__ = "products"
    __table_args__ = (
        Index("idx_products_category_id", "category_id"),
        Index("idx_products_active_id", "is_active", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    category: Mapped[CategoryModel | None] = relationship(
        "CategoryModel", back_populates="products"
    )
    images: Mapped[list["ProductImageModel"]] = relationship(
        "ProductImageModel", back_populates="product", cascade="all, delete-orphan"
    )
    tags: Mapped[list[TagModel]] = relationship(
        "TagModel", secondary="product_tags", back_populates="products"
    )
    attribute_values: Mapped[list["ProductAttributeValueModel"]] = relationship(
        "ProductAttributeValueModel",
        back_populates="product",
        cascade="all, delete-orphan",
    )


class ProductImageModel(Base):
    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)

    product: Mapped[ProductModel] = relationship(
        "ProductModel", back_populates="images"
    )


class ProductAttributeValueModel(Base):
    __tablename__ = "product_attribute_values"
    __table_args__ = (
        UniqueConstraint("product_id", "attribute_id", name="uq_product_attribute_value"),
        Index("idx_product_attribute_values_attribute_id", "attribute_id"),
        Index("idx_product_attribute_values_text", "attribute_id", "value_text"),
        Index("idx_product_attribute_values_number", "attribute_id", "value_number"),
        Index("idx_product_attribute_values_bool", "attribute_id", "value_bool"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    attribute_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("category_attributes.id", ondelete="CASCADE"), nullable=False
    )
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_number: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_bool: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    value_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)

    product: Mapped[ProductModel] = relationship(
        "ProductModel", back_populates="attribute_values"
    )
    attribute: Mapped[CategoryAttributeModel] = relationship(
        "CategoryAttributeModel", back_populates="values"
    )
