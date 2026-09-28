"""Schema contract tests for SourceCraft identifiers up to 128 characters."""

import unittest
from unittest.mock import patch

from alembic.config import Config
from alembic.script import ScriptDirectory

from sourcehealth.storage.models import Repository


class SourceCraftSlugSchemaContractTests(unittest.TestCase):
    def test_migration_is_the_only_alembic_head(self):
        scripts = ScriptDirectory.from_config(Config("alembic.ini"))
        self.assertEqual(scripts.get_heads(), ["0004_sourcecraft_slug_contract"])

    def test_upgrade_matches_model_without_recreating_constraints(self):
        scripts = ScriptDirectory.from_config(Config("alembic.ini"))
        migration = scripts.get_revision(scripts.get_current_head()).module
        with patch.object(migration.op, "alter_column") as alter:
            migration.upgrade()

        self.assertEqual(alter.call_count, 3)
        changes = {call.args[1]: call.kwargs for call in alter.call_args_list}
        self.assertEqual(set(changes), {
            "organization_slug", "repository_slug", "project_slug",
        })
        for name, kwargs in changes.items():
            self.assertEqual(kwargs["existing_type"].length, 100)
            self.assertEqual(kwargs["type_"].length, 128)
            self.assertEqual(Repository.__table__.c[name].type.length, 128)


if __name__ == "__main__":
    unittest.main()
