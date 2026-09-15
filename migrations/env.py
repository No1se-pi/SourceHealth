"""Alembic использует typed settings и ту же metadata; create_all не применяется."""

from alembic import context
from sqlalchemy import create_engine, pool

from sourcehealth.settings import Settings
from sourcehealth.storage.models import Base

url = Settings().database_url.get_secret_value()
if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool, hide_parameters=True, connect_args={"connect_timeout": 10})
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
