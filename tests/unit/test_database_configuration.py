from __future__ import annotations

import unittest

from emotv.config import get_database_url


class DatabaseConfigurationTests(unittest.TestCase):
    def test_reads_database_url_from_environment_mapping(self) -> None:
        url = get_database_url(
            {
                "DATABASE_URL": (
                    "postgresql+psycopg://emotv:secret@localhost:5432/emotv"
                )
            }
        )

        self.assertEqual(
            url,
            "postgresql+psycopg://emotv:secret@localhost:5432/emotv",
        )

    def test_strips_surrounding_whitespace(self) -> None:
        url = get_database_url({"DATABASE_URL": "  postgresql://localhost/db  "})

        self.assertEqual(url, "postgresql://localhost/db")

    def test_rejects_missing_or_empty_database_url(self) -> None:
        for environ in ({}, {"DATABASE_URL": "   "}):
            with self.subTest(environ=environ):
                with self.assertRaisesRegex(RuntimeError, "DATABASE_URL"):
                    get_database_url(environ)


if __name__ == "__main__":
    unittest.main()
