"""Engine/session factory принадлежит процессу API/worker, а не глобальному core."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def create_database(url: str, *, statement_timeout: int | None = None):
    if not url.startswith("postgresql+psycopg://"):
        raise ValueError("PostgreSQL with psycopg is required")
    connect_args = {"connect_timeout": 10}
    if statement_timeout is not None:
        if type(statement_timeout) is not int or statement_timeout <= 0:
            raise ValueError("positive statement timeout required")
        # Operator polling/import must not wait indefinitely on another transaction's lock.
        connect_args["options"] = f"-c statement_timeout={statement_timeout} -c lock_timeout={statement_timeout}"
    engine = create_engine(url, pool_pre_ping=True, hide_parameters=True, connect_args=connect_args)
    return engine, sessionmaker(engine, expire_on_commit=False)
