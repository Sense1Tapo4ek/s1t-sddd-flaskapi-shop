"""
Declarative seed script.

Reads data/seed_config.yaml and generates mock data for the shop database.
Always creates the default admin user and system settings (non-configurable).
Skips entities that already have data (idempotent).

Supported field types in seed_config.yaml:
  choice          — random pick from "values" list
  enum            — alias for choice
  range           — random float in [min, max] with "precision" decimals
  int_range       — random int in [min, max]
  pattern         — string template: {d2}=2 digits, {d3}=3 digits, {d4}=4 digits
  sequence        — "{prefix}{i}" where i is 1..count
  fixed           — always the same "value"
  lorem           — random sentence built from lorem words (fallback)
  faker           — any Faker method: { method: name, locale: ru_RU }
  download_images — download real JPEGs from picsum.photos and save locally
  placeholder_images — picsum URLs without downloading (offline-safe fallback)

Usage:
    PYTHONPATH=src python data/seed.py
"""

import os
import random
import re
import sys
import uuid
from pathlib import Path

import httpx
import yaml
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash

sys.path.append(os.path.join(os.getcwd(), "src"))

from access.adapters.driven.db.models import UserModel
from access.config import AccessConfig
from catalog.adapters.driven.db.models import ProductModel, ProductImageModel
from ordering.adapters.driven.db.models import OrderModel
from shared.adapters.driven.db.base import Base
from system.adapters.driven.db.models import SettingsModel

SEED_CONFIG_PATH = Path(__file__).parent / "seed_config.yaml"
DEFAULT_LOCALE = "ru_RU"

ENTITY_REGISTRY = {
    "products": {
        "model": ProductModel,
        "columns": ["title", "price", "description"],
        "has_images": True,
    },
    "orders": {
        "model": OrderModel,
        "columns": ["name", "phone", "comment", "status"],
        "has_images": False,
    },
}


# ---------------------------------------------------------------------------
# Faker factory (cached by locale)
# ---------------------------------------------------------------------------

_faker_cache: dict = {}


def _get_faker(locale: str | None = None):
    from faker import Faker

    loc = locale or DEFAULT_LOCALE
    if loc not in _faker_cache:
        _faker_cache[loc] = Faker(loc)
    return _faker_cache[loc]


# ---------------------------------------------------------------------------
# Field generators
# ---------------------------------------------------------------------------

def _gen_choice(spec: dict) -> str:
    return random.choice(spec["values"])


def _gen_range(spec: dict) -> float:
    precision = spec.get("precision", 2)
    return round(random.uniform(spec["min"], spec["max"]), precision)


def _gen_int_range(spec: dict) -> int:
    return random.randint(spec["min"], spec["max"])


def _gen_pattern(spec: dict, index: int = 0) -> str:
    result = spec["template"]
    result = re.sub(r"\{d(\d)\}", lambda m: _random_digits(int(m.group(1))), result)
    return result


def _gen_sequence(spec: dict, index: int = 0) -> str:
    return f"{spec.get('prefix', '')}{index}"


def _gen_fixed(spec: dict) -> str:
    return spec["value"]


def _gen_lorem(spec: dict) -> str:
    words = spec.get("words", 10)
    pool = "лорем ипсум долор сит амет консектетур адипискинг элит мод до эиусмод темпор инцидидунт ут лаборе эт долоре магна аликуа".split()
    return " ".join(random.choice(pool) for _ in range(words)).capitalize() + "."


def _gen_faker(spec: dict) -> str:
    """
    Call any Faker method by name.
    spec example: { method: name, locale: ru_RU }
    """
    faker = _get_faker(spec.get("locale"))
    method = spec.get("method", "word")
    fn = getattr(faker, method, None)
    if fn is None:
        raise ValueError(f"Faker has no method '{method}'")
    return str(fn())


def _gen_download_images(spec: dict) -> list[str]:
    """
    Download real low-quality images from picsum.photos and save them locally.
    Falls back to a picsum URL (no file saved) if the request fails.
    """
    count = random.randint(spec.get("min", 1), spec.get("max", 3))
    w = spec.get("width", 300)
    h = spec.get("height", 300)

    upload_dir = os.environ.get("CATALOG_UPLOAD_DIR", "media/products")
    os.makedirs(upload_dir, exist_ok=True)

    paths = []
    for _ in range(count):
        lock = random.randint(1, 9999)
        url = f"https://loremflickr.com/{w}/{h}?lock={lock}"
        try:
            resp = httpx.get(url, follow_redirects=True, timeout=15)
            resp.raise_for_status()
            filename = f"seed_{uuid.uuid4().hex}.jpg"
            file_path = os.path.join(upload_dir, filename)
            with open(file_path, "wb") as f:
                f.write(resp.content)
            paths.append(f"/media/products/{filename}")
            print(f"    [img] Скачано → {filename}")
        except Exception as e:
            fallback = f"https://picsum.photos/seed/{lock}/{w}/{h}"
            print(f"    [img] Ошибка скачивания ({e}), URL-фоллбэк")
            paths.append(fallback)

    return paths


def _gen_placeholder_images(spec: dict) -> list[str]:
    """Offline-safe fallback: picsum URLs without downloading."""
    count = random.randint(spec.get("min", 1), spec.get("max", 3))
    w = spec.get("width", 300)
    h = spec.get("height", 300)
    return [
        f"https://picsum.photos/seed/{random.randint(1, 9999)}/{w}/{h}"
        for _ in range(count)
    ]


def _random_digits(n: int) -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(n))


GENERATORS = {
    "choice": _gen_choice,
    "enum": _gen_choice,
    "range": _gen_range,
    "int_range": _gen_int_range,
    "pattern": _gen_pattern,
    "sequence": _gen_sequence,
    "fixed": _gen_fixed,
    "lorem": _gen_lorem,
    "faker": _gen_faker,
    "download_images": _gen_download_images,
    "placeholder_images": _gen_placeholder_images,
}


def generate_field(spec: dict, index: int = 0):
    field_type = spec["type"]
    gen = GENERATORS.get(field_type)
    if gen is None:
        raise ValueError(f"Unknown field type: '{field_type}'")
    if field_type in ("pattern", "sequence"):
        return gen(spec, index)
    return gen(spec)


# ---------------------------------------------------------------------------
# Core seed logic
# ---------------------------------------------------------------------------

def _ensure_defaults(session: Session, access_config: AccessConfig) -> None:
    admin_count = session.execute(select(func.count(UserModel.id))).scalar()
    if admin_count == 0:
        admin = UserModel(
            login=access_config.default_login,
            password_hash=generate_password_hash(access_config.default_password),
        )
        session.add(admin)
        session.commit()
        print(
            f"  [admin] Создан: {access_config.default_login} / "
            f"{access_config.default_password}"
        )

    settings = session.execute(
        select(SettingsModel).where(SettingsModel.id == 1)
    ).scalar()
    if not settings:
        session.add(SettingsModel(
            id=1,
            phone="+7 555 000-00-00",
            email="admin@example.com",
            address="ул. Ленина, 1, Москва",
            working_hours="Пн–Пт 09:00 – 18:00",
        ))
        session.commit()
        print("  [system] Системные настройки созданы")


def _seed_entity(session: Session, entity_name: str, entity_cfg: dict) -> None:
    registry = ENTITY_REGISTRY.get(entity_name)
    if registry is None:
        print(f"  [skip] Неизвестная сущность '{entity_name}' — не зарегистрирована в ENTITY_REGISTRY")
        return

    model = registry["model"]
    columns = registry["columns"]
    has_images = registry.get("has_images", False)

    existing = session.execute(select(func.count(model.id))).scalar()
    if existing > 0:
        print(f"  [{entity_name}] Уже есть {existing} записей — пропускаем")
        return

    count = entity_cfg.get("count", 5)
    fields_cfg = entity_cfg.get("fields", {})
    created = 0

    for i in range(1, count + 1):
        kwargs = {}
        images_spec = None

        for field_name, spec in fields_cfg.items():
            if field_name == "images":
                images_spec = spec
                continue
            if field_name in columns:
                kwargs[field_name] = generate_field(spec, index=i)

        row = model(**kwargs)
        session.add(row)
        session.flush()

        if has_images and images_spec is not None:
            image_paths = generate_field(images_spec)
            for path in image_paths:
                session.add(ProductImageModel(product_id=row.id, file_path=path))

        created += 1

    session.commit()
    print(f"  [{entity_name}] Создано {created} записей")


def seed():
    access_config = AccessConfig()

    os.makedirs("media/products", exist_ok=True)
    os.makedirs("data", exist_ok=True)

    db_url = os.environ.get("INFRA_DATABASE_URL", "sqlite:///data/shop.db")
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)

    print("Заполнение базы данных...")

    with Session(engine) as session:
        _ensure_defaults(session, access_config)

        if not SEED_CONFIG_PATH.exists():
            print(f"  [warn] {SEED_CONFIG_PATH} не найден — пропускаем генерацию моков")
            return

        with open(SEED_CONFIG_PATH) as f:
            config = yaml.safe_load(f) or {}

        for entity_name, entity_cfg in config.items():
            print(f"  [{entity_name}] Генерация...")
            _seed_entity(session, entity_name, entity_cfg)

    print("Готово.")


if __name__ == "__main__":
    seed()
