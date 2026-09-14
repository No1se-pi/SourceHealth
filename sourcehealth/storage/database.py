"""Engine/session factory принадлежит процессу API/worker, а не глобальному core."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def create_database(url: str):
    if not url.startswith("postgresql+psycopg://"):
        raise ValueError("PostgreSQL with psycopg is required")
    engine = create_engine(url, pool_pre_ping=True, hide_parameters=True, connect_args={"connect_timeout": 10})
    return engine, sessionmaker(engine, expire_on_commit=False)
