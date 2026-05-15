from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


MYSQL_TABLE_OPTS: dict[str, str] = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def mysql_table_opts() -> dict[str, str]:
    """InnoDB + utf8mb4 options to append into __table_args__.

    Usage:
        __table_args__ = (UniqueConstraint(...), Index(...), mysql_table_opts())
        __table_args__ = (CheckConstraint(...), mysql_table_opts())
    """
    return dict(MYSQL_TABLE_OPTS)
