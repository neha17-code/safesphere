import unittest

from app.config import normalise_db_url


class DbUrl(unittest.TestCase):
    def test_render_style_postgres_url(self):
        self.assertEqual(normalise_db_url("postgres://u:p@host:5432/db"),
                         "postgresql+psycopg://u:p@host:5432/db")

    def test_plain_postgresql_url(self):
        self.assertEqual(normalise_db_url("postgresql://u:p@host/db?sslmode=require"),
                         "postgresql+psycopg://u:p@host/db?sslmode=require")

    def test_already_correct_and_sqlite_untouched(self):
        self.assertEqual(normalise_db_url("postgresql+psycopg://u:p@h/db"), "postgresql+psycopg://u:p@h/db")
        self.assertEqual(normalise_db_url("sqlite:///./x.db"), "sqlite:///./x.db")


if __name__ == "__main__":
    unittest.main()
