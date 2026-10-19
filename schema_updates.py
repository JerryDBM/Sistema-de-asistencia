from sqlalchemy import inspect, text

from database import Base, engine


def initialize_schema() -> None:
    """Create new tables and safely add the professor link to legacy classes."""
    # Create the referenced table first so the legacy classes migration can run
    # before create_all attempts to build the new professor_id index.
    from models import User

    Base.metadata.create_all(bind=engine, tables=[User.__table__])
    inspector = inspect(engine)
    dialect = engine.dialect.name
    if "clases" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("clases")}
        if "professor_id" not in columns:
            with engine.begin() as connection:
                if dialect == "mysql":
                    connection.execute(text("ALTER TABLE clases ADD COLUMN professor_id INTEGER NULL"))
                    connection.execute(text(
                        "ALTER TABLE clases ADD CONSTRAINT fk_clases_professor "
                        "FOREIGN KEY (professor_id) REFERENCES usuarios (id) ON DELETE SET NULL"
                    ))
                    connection.execute(text("CREATE INDEX ix_clases_professor_id ON clases (professor_id)"))
                elif dialect == "sqlite":
                    connection.execute(text(
                        "ALTER TABLE clases ADD COLUMN professor_id INTEGER "
                        "REFERENCES usuarios (id) ON DELETE SET NULL"
                    ))
                else:
                    raise RuntimeError(f"Migración de clases no soportada para {dialect}.")
    Base.metadata.create_all(bind=engine)
