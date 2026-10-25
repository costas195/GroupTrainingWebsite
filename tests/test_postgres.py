"""Run the same business rules against isolated real PostgreSQL schemas.

Set TEST_DATABASE_URL to a dedicated test database. Never use the live database.
"""
import os
import unittest
import uuid

import psycopg
from psycopg import sql

from database import Connection
import test_portal
import test_invitations


class PostgresSchema:
    def setUp(self):
        self.schema = 'test_form_' + uuid.uuid4().hex
        self.test_url = os.environ['TEST_DATABASE_URL']
        with psycopg.connect(self.test_url, connect_timeout=5) as connection:
            connection.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
        self.addCleanup(self.drop_schema)
        super().setUp()

    def drop_schema(self):
        if not self.schema.startswith('test_form_'):
            raise RuntimeError('Refusing to drop an unexpected schema.')
        with psycopg.connect(self.test_url, connect_timeout=5) as connection:
            connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))

    def database_config(self):
        return {'DATABASE_URL': self.test_url, 'DATABASE_SCHEMA': self.schema}

    def app_config(self):
        config = super().app_config()
        config.update(self.database_config())
        return config

    def connect_db(self):
        return Connection(self.app.config)

    def execute(self, statement, parameters=()):
        with self.connect_db() as connection:
            rows = connection.execute(statement, parameters).fetchall() if statement.lstrip().upper().startswith('SELECT') else None
            if rows is None:
                connection.execute(statement, parameters)
        connection.close()
        return [tuple(row.values()) for row in rows] if rows is not None else []


@unittest.skipUnless(os.getenv('TEST_DATABASE_URL'), 'Set TEST_DATABASE_URL to run PostgreSQL integration checks.')
class PostgresPortalTests(PostgresSchema, test_portal.PortalTests):
    pass


@unittest.skipUnless(os.getenv('TEST_DATABASE_URL'), 'Set TEST_DATABASE_URL to run PostgreSQL integration checks.')
class PostgresInvitationTests(PostgresSchema, test_invitations.InvitationTests):
    pass
