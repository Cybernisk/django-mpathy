from psycopg2.extensions import quote_ident

from django.apps import apps as global_apps
from django.contrib.postgres.operations import CreateExtension
from django.db import connection, DEFAULT_DB_ALIAS, migrations

from .fields import LTreeField


class LTreeExtension(CreateExtension):

    def __init__(self):
        self.name = 'ltree'


def inject_pre_migration_operations(plan=None, apps=global_apps, using=DEFAULT_DB_ALIAS, **kwargs):
    """
    Insert a `LTreeExtension` operation before every planned `CreateModel` operation.
    """
    if plan is None:
        return

    for migration, backward in plan:
        for index, operation in enumerate(migration.operations):
            if isinstance(operation, migrations.CreateModel):
                for name, field in operation.fields:
                    if isinstance(field, LTreeField):
                        migration.operations.insert(index, LTreeExtension())
                        return


def post_migrate_add_check_constraint(model):
    names = {
        "table": quote_ident(model._meta.db_table, connection.connection),
        "constraint": quote_ident('%s__check_ltree' % model._meta.db_table, connection.connection),
    }

    cur = connection.cursor()
    # Check that the ltree is always consistent with being a child of _parent
    cur.execute('''
        ALTER TABLE %(table)s ADD CONSTRAINT %(constraint)s CHECK (
            (_parent_id IS NOT NULL AND ltree ~ (_parent_id::text || '.*{1}')::lquery)
            OR (_parent_id IS NULL AND ltree ~ '*{1}'::lquery)
        )
    ''' % names)


def inject_post_migration_operations(plan=None, apps=global_apps, using=DEFAULT_DB_ALIAS, **kwargs):
    if plan is None:
        return

    for migration, backward in plan:
        for index, operation in reversed(list(enumerate(migration.operations))):
            if isinstance(operation, migrations.CreateModel):
                model = apps.get_model(migration.app_label, operation.name)
                post_migrate_add_check_constraint(model)
