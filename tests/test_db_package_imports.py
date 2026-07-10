import importlib


def test_db_modules_import_cleanly() -> None:
    connection = importlib.import_module("db.connection")
    recovery = importlib.import_module("db.recovery")
    writer = importlib.import_module("db.writer")

    assert hasattr(connection, "run_migrations")
    assert hasattr(connection, "get_async_connection")
    assert hasattr(recovery, "DatabaseRecovery")
    assert hasattr(writer, "write_position_opened")
