"""Unit tests for database URL construction without live servers."""

import os
import unittest
from unittest.mock import patch

from src.database.postgres import create_postgres_engine
from src.database.sqlserver import create_sqlserver_engine


class DatabaseConfigurationTests(unittest.TestCase):
    @patch.dict(os.environ, {"POSTGRES_PASSWORD": "p@ss/word"}, clear=True)
    def test_postgres_url_escapes_credentials(self) -> None:
        engine = create_postgres_engine()
        self.assertEqual(engine.url.drivername, "postgresql+psycopg")
        self.assertEqual(engine.url.password, "p@ss/word")
        self.assertEqual(engine.url.database, "supply_chain")

    @patch.dict(os.environ, {"SQLSERVER_PASSWORD": "p@ss/word"}, clear=True)
    def test_sqlserver_url_has_odbc_driver(self) -> None:
        engine = create_sqlserver_engine()
        self.assertEqual(engine.url.drivername, "mssql+pyodbc")
        self.assertEqual(engine.url.password, "p@ss/word")
        self.assertEqual(engine.url.query["driver"], "ODBC Driver 18 for SQL Server")

    @patch.dict(os.environ, {}, clear=True)
    def test_passwords_are_required(self) -> None:
        with self.assertRaises(ValueError):
            create_postgres_engine()
        with self.assertRaises(ValueError):
            create_sqlserver_engine()


if __name__ == "__main__":
    unittest.main()
