"""Show results from test_config.py — PostgresConfig pure logic tests."""

import os

import pytest

from adapters.postgres.config import PostgresConfig


class TestPostgresConfig:
    def test_defaults(self):
        c = PostgresConfig()
        assert c.host == "localhost"
        assert c.port == 5432
        assert c.database == "pl_agent"
        assert c.user == "postgres"
        assert c.password == ""

    def test_dsn_no_password(self):
        c = PostgresConfig(host="db", port=5433, database="test", user="app")
        assert c.dsn == "postgresql://app@db:5433/test"

    def test_dsn_with_password(self):
        c = PostgresConfig(password="secret", database="test", user="app")
        assert c.dsn == "postgresql://app:secret@localhost:5432/test"

    def test_from_url_full(self):
        url = "postgresql://user:pass@host:5555/mydb"
        c = PostgresConfig.from_url(url)
        assert c.host == "host"
        assert c.port == 5555
        assert c.database == "mydb"
        assert c.user == "user"
        assert c.password == "pass"

    def test_from_url_no_password(self):
        c = PostgresConfig.from_url("postgresql://admin@localhost/mydb")
        assert c.user == "admin"
        assert c.password == ""
        assert c.port == 5432

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("PGHOST", "pg.example.com")
        monkeypatch.setenv("PGPORT", "5433")
        monkeypatch.setenv("PGDATABASE", "palworld")
        monkeypatch.setenv("PGUSER", "pal_admin")
        monkeypatch.setenv("PGPASSWORD", "s3cret")

        c = PostgresConfig.from_env()
        assert c.host == "pg.example.com"
        assert c.port == 5433
        assert c.database == "palworld"
        assert c.user == "pal_admin"
        assert c.password == "s3cret"

    def test_from_env_database_url_priority(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://url_user@url_host/url_db")
        monkeypatch.setenv("PGHOST", "ignored")

        c = PostgresConfig.from_env()
        assert c.host == "url_host"
        assert c.database == "url_db"
        assert c.user == "url_user"

    def test_from_env_defaults(self, monkeypatch):
        # clear all env vars
        for key in (
            "DATABASE_URL",
            "PGHOST",
            "PGPORT",
            "PGDATABASE",
            "PGUSER",
            "PGPASSWORD",
        ):
            monkeypatch.delenv(key, raising=False)

        c = PostgresConfig.from_env()
        assert c.host == "localhost"
        assert c.port == 5432
