from __future__ import annotations

import unittest

from support import TitleTestCase
from zcode_adapter import SCHEMA, schema_field_names
from archive_policy import SCHEMA as ARCHIVE_SCHEMA


class SchemaPromptTests(TitleTestCase):
    def test_naming_schema_fields(self):
        self.assertEqual(schema_field_names(SCHEMA), ["action", "title", "reason"])

    def test_archive_schema_fields_are_not_naming_fields(self):
        self.assertEqual(schema_field_names(ARCHIVE_SCHEMA), ["classification", "reason"])
        self.assertNotEqual(schema_field_names(ARCHIVE_SCHEMA), schema_field_names(SCHEMA))


if __name__ == "__main__":
    unittest.main()
