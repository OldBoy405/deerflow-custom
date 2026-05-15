from __future__ import annotations

import datetime as dt
import decimal
import json
import os
import re
from dataclasses import dataclass
from typing import Any

from mcp.server.fastmcp import FastMCP
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError


mcp = FastMCP("sqlserver-mcp")

_WRITE_SQL_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|merge|exec|execute|grant|revoke)\b",
    re.IGNORECASE,
)
_SELECT_SQL_RE = re.compile(r"^\s*(with\b[\s\S]*?\bselect\b|select\b)", re.IGNORECASE)


@dataclass(frozen=True)
class SqlServerConfig:
    host: str
    port: int
    database: str
    username: str
    password: str
    driver: str
    encrypt: bool
    trust_server_certificate: bool
    connect_timeout: int


def _to_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_sqlserver_cfg() -> SqlServerConfig:
    default_cfg: dict[str, Any] = {
        "host": "",
        "port": 1433,
        "database": "",
        "username": "",
        "password": "",
        "driver": "ODBC Driver 17 for SQL Server",
        "encrypt": False,
        "trust_server_certificate": True,
        "connect_timeout": 10,
    }

    cfg_path = os.getenv(
        "SQLSERVER_CONFIG_PATH",
        os.path.join(os.path.dirname(__file__), "sqlserver_config.json"),
    )
    file_cfg: dict[str, Any] = {}
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                file_cfg = loaded
        except Exception:
            # Ignore broken local file and let env/defaults work.
            file_cfg = {}

    env_cfg: dict[str, Any] = {
        "host": os.getenv("SQLSERVER_HOST"),
        "port": os.getenv("SQLSERVER_PORT"),
        "database": os.getenv("SQLSERVER_DATABASE"),
        "username": os.getenv("SQLSERVER_USERNAME"),
        "password": os.getenv("SQLSERVER_PASSWORD"),
        "driver": os.getenv("SQLSERVER_DRIVER"),
        "encrypt": os.getenv("SQLSERVER_ENCRYPT"),
        "trust_server_certificate": os.getenv("SQLSERVER_TRUST_SERVER_CERTIFICATE"),
        "connect_timeout": os.getenv("SQLSERVER_CONNECT_TIMEOUT"),
    }

    merged = {**default_cfg, **file_cfg, **{k: v for k, v in env_cfg.items() if v not in (None, "")}}
    return SqlServerConfig(
        host=str(merged["host"]).strip(),
        port=_to_int(merged["port"], 1433),
        database=str(merged["database"]).strip(),
        username=str(merged["username"]).strip(),
        password=str(merged["password"]),
        driver=str(merged["driver"]).strip(),
        encrypt=_to_bool(merged["encrypt"], False),
        trust_server_certificate=_to_bool(merged["trust_server_certificate"], True),
        connect_timeout=_to_int(merged["connect_timeout"], 10),
    )


def _validate_cfg(cfg: SqlServerConfig) -> None:
    missing = [
        key
        for key, value in {
            "SQLSERVER_HOST": cfg.host,
            "SQLSERVER_DATABASE": cfg.database,
            "SQLSERVER_USERNAME": cfg.username,
            "SQLSERVER_PASSWORD": cfg.password,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(f"Missing required SQL Server config: {', '.join(missing)}")


def _build_mssql_sqlalchemy_url(cfg: SqlServerConfig) -> URL:
    _validate_cfg(cfg)
    encrypt = "yes" if cfg.encrypt else "no"
    trust = "yes" if cfg.trust_server_certificate else "no"
    timeout = str(max(1, cfg.connect_timeout))
    return URL.create(
        "mssql+pyodbc",
        username=cfg.username,
        password=cfg.password,
        host=cfg.host,
        port=cfg.port,
        database=cfg.database,
        query={
            "driver": cfg.driver,
            "Encrypt": encrypt,
            "TrustServerCertificate": trust,
            "Connection Timeout": timeout,
        },
    )


def _make_engine():
    cfg = _load_sqlserver_cfg()
    url = _build_mssql_sqlalchemy_url(cfg)
    engine = create_engine(url, pool_pre_ping=True)
    return engine, cfg


def _serialize_value(value: Any) -> Any:
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _validate_readonly_sql(sql_input: str) -> str:
    sql = (sql_input or "").strip()
    if not sql:
        raise ValueError("sql_input must not be empty.")
    if not _SELECT_SQL_RE.search(sql):
        raise ValueError("Only read-only SELECT/CTE-SELECT statements are allowed.")
    if _WRITE_SQL_RE.search(sql):
        raise ValueError("Write/DDL statements are not allowed.")
    return sql


def _cap_limit(limit: int) -> int:
    return max(1, min(int(limit), 100))


@mcp.tool()
def health_check() -> dict[str, Any]:
    """Check SQL Server connectivity and basic runtime info."""
    try:
        engine, cfg = _make_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 AS ok"))
        return {
            "ok": True,
            "target": f"{cfg.host}:{cfg.port}/{cfg.database}",
            "driver": cfg.driver,
        }
    except Exception as e:
        return {"ok": False, "error_type": type(e).__name__, "error": str(e)}


@mcp.tool()
def execute_sql(sql_input: str, limit: int = 100) -> dict[str, Any]:
    """Execute a read-only SQL query and return structured rows."""
    rows_limit = _cap_limit(limit)
    try:
        sql = _validate_readonly_sql(sql_input)
        engine, cfg = _make_engine()
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            columns = list(result.keys())
            fetched_maps = result.mappings().fetchmany(rows_limit + 1)

        truncated = len(fetched_maps) > rows_limit
        serialized_rows = [
            {col: _serialize_value(m[col]) for col in columns}
            for m in fetched_maps[:rows_limit]
        ]

        return {
            "ok": True,
            "columns": columns,
            "rows": serialized_rows,
            # "row_count": len(serialized_rows),
            "truncated": truncated,
            "limit": rows_limit,
            "target": f"{cfg.host}:{cfg.port}/{cfg.database}",
        }
    except (ValueError, SQLAlchemyError) as e:
        return {"ok": False, "error_type": type(e).__name__, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error_type": type(e).__name__, "error": str(e)}


@mcp.tool()
def describe_table(table_name: str, schema_name: str = "dbo") -> dict[str, Any]:
    """Describe table columns from INFORMATION_SCHEMA.COLUMNS."""
    if not table_name.strip():
        return {"ok": False, "error": "table_name must not be empty"}

    sql = """
    SELECT
      COLUMN_NAME,
      DATA_TYPE,
      IS_NULLABLE,
      CHARACTER_MAXIMUM_LENGTH,
      NUMERIC_PRECISION,
      NUMERIC_SCALE
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = :schema_name
      AND TABLE_NAME = :table_name
    ORDER BY ORDINAL_POSITION
    """
    try:
        engine, _cfg = _make_engine()
        with engine.connect() as conn:
            result = conn.execute(
                text(sql),
                {"schema_name": schema_name.strip(), "table_name": table_name.strip()},
            )
            rows = [dict(row._mapping) for row in result.fetchall()]

        return {
            "ok": True,
            "schema_name": schema_name.strip(),
            "table_name": table_name.strip(),
            "columns": rows,
            "column_count": len(rows),
        }
    except Exception as e:
        return {"ok": False, "error_type": type(e).__name__, "error": str(e)}


if __name__ == "__main__":
    mcp.run(transport="stdio")
