"""Tests for schema migrations."""
from knowledge_master.migrations import (
    CURRENT_SCHEMA_VERSION,
    MIGRATIONS,
    _migrate_to_v1,
    _migrate_to_v3,
    _migrate_to_v4,
)


def test_current_schema_version():
    assert CURRENT_SCHEMA_VERSION == 4


def test_all_migrations_defined():
    for v in range(1, CURRENT_SCHEMA_VERSION + 1):
        assert v in MIGRATIONS, f"Migration to v{v} not defined"


def test_migrations_are_callable():
    for v, fn in MIGRATIONS.items():
        assert callable(fn)
        assert fn.__doc__ is not None, f"Migration v{v} has no docstring"
