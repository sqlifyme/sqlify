import sqlite3
import os
import json
from contextlib import contextmanager
from sqletl.datatable import DataTable
from .db import Database, node_handler, ddl_only
from .parser import parse
from . import ast


class ServerDatabase(Database):
    def __init__(self, *args, **kwargs):
        self.server = kwargs.pop("server")
        self.role = kwargs.pop("role")
        super().__init__(*args, **kwargs)


class AuthenticatedDatabase(ServerDatabase):
    @node_handler(ast.Show, lambda node: (node.type, node.name))
    def show(self, type, name=None):
        if type == "databases":
            dbs = self.server.get_databases() if self.role == "system" else self.server.get_databases_for_role(self.role)
            return DataTable(["database"], [[d] for d in dbs])
        return super().show(type, name)


class SystemDatabase(AuthenticatedDatabase):
    @node_handler(ast.CreateDatabase, lambda node: (node.name,))
    @ddl_only
    def create_database(self, database):
        self.server.create_database(database)
    
    @node_handler(ast.DropDatabase, lambda node: (node.name,))
    @ddl_only
    def drop_database(self, database):
        self.server.drop_database(database)
        
    @node_handler(ast.CreateRole, lambda node: (node.role, node.password))
    @ddl_only
    def create_role(self, role, password=None):
        self.server.create_role(role, password)

    @node_handler(ast.AlterRole, lambda node: (node.role, node.password))
    @ddl_only
    def alter_role(self, role, password=None):
        self.server.alter_role(role, password)

    @node_handler(ast.DropRole, lambda node: (node.role, node.with_database))
    @ddl_only
    def drop_role(self, role, with_databases=False):
        self.server.drop_role(role, with_databases)
        
    @node_handler(ast.Grant, lambda node: (node.role, node.database, node.is_admin, node.alias))
    @ddl_only
    def grant(self, role, database, is_admin=False, alias=None):
        self.server.grant(role, database, is_admin, alias)
        
    @node_handler(ast.Revoke, lambda node: (node.role, node.database))
    @ddl_only
    def revoke(self, role, database):
        self.server.revoke(role, database)


class Server:
    def __init__(self, sqlite_uri, files_dir=None, system_pwd=None):
        self.sqlite_uri = sqlite_uri
        self.files_dir = files_dir if files_dir else os.path.join(os.path.dirname(sqlite_uri), "user_files")
        self.system_pwd = system_pwd
        if not system_pwd:
            self.system_pwd = os.environ.get("SQLETL_DB_SYSTEM_PWD")
        if not os.path.exists(self.sqlite_uri):
            self.create_schema()

    @contextmanager
    def cursor(self, cursor=None):
        conn = None
        if not cursor:
            conn = sqlite3.connect(self.sqlite_uri)
            cursor = conn.cursor()
        yield (conn, cursor)
        if conn:
            cursor.close()
            conn.close()

    def create_schema(self):
        with self.cursor() as (conn, cursor):
            cursor.execute("CREATE TABLE databases (name TEXT PRIMARY KEY, config JSON)")
            cursor.execute("CREATE TABLE roles (role TEXT PRIMARY KEY, password TEXT)")
            cursor.execute("CREATE TABLE grants (role TEXT, database TEXT, is_admin BOOLEAN DEFAULT 0, alias TEXT)")
            cursor.execute("CREATE UNIQUE INDEX grants_role_database ON grants (role, database)")
            cursor.execute("CREATE UNIQUE INDEX grants_role_alias ON grants (role, alias)")
            conn.commit()
        
    def authenticate(self, role, password, database):
        if role == "system":
            return self.system_pwd and password == self.system_pwd
        with self.cursor() as (conn, cursor):
            cursor.execute("""SELECT 1 FROM roles JOIN grants ON grants.role = roles.role
                              WHERE grants.role = ? AND (grants.database = ? OR grants.alias = ?)
                                AND roles.password IS NOT NULL AND roles.password = ? """, (role, database, database, password))
            return cursor.fetchone() is not None
    
    def execute(self, database, role, query):
        if isinstance(query, str):
            query = parse(query)
        db = self.get_database_for_role(role, database)
        if not db:
            raise Exception(f"Role {role} has no access to database {database}")
        return db.execute(query)

    def create_database(self, database, role=None, cursor=None):
        with self.cursor(cursor) as (conn, cursor):
            cursor.execute("INSERT INTO databases (name, config) VALUES (?, ?)", (database, '{}'))
            conn.commit()
            if role:
                self.grant(role, database, is_admin=True, cursor=cursor)
            return self.get_database(database, cursor=cursor)
        
    def drop_database(self, database):
        with self.cursor() as (conn, cursor):
            cursor.execute("DELETE FROM databases WHERE name = ?", (database,))
            cursor.execute("DELETE FROM grants WHERE database = ?", (database,))
            conn.commit()

    def get_databases(self):
        with self.cursor() as (conn, cursor):
            cursor.execute("SELECT name FROM databases")
            return [row[0] for row in cursor.fetchall()]

    def get_database(self, database, ddl_allowed=True, role=None, cursor=None):
        if database == "system":
            return SystemDatabase(name="system", ddl_allowed=True, role=role, server=self)
        with self.cursor(cursor) as (conn, cursor):
            cursor.execute(("SELECT config FROM databases WHERE name = ?"), (database,))
            row = cursor.fetchone()
            if not row:
                return None
            db_class = ServerDatabase if not role else AuthenticatedDatabase
            return db_class.from_config(json.loads(row[0]),
                                    name=database,
                                    ddl_allowed=False if not role else ddl_allowed,
                                    ddl_callback=self._make_ddl_callback(database),
                                    files_dir=os.path.join(self.files_dir, database),
                                    server=self,
                                    role=role)
        
    def _make_ddl_callback(self, database):
        def ddl_callback(db):
            with self.cursor() as (conn, cursor):
                cursor.execute("UPDATE databases SET config = ? WHERE name = ?", (json.dumps(db.as_config()), database))
                conn.commit()
        return ddl_callback
        
    def create_role(self, role, password=None, cursor=None):
        with self.cursor(cursor) as (conn, cursor):
            cursor.execute("INSERT INTO roles (role, password) VALUES (?, ?)", (role, password))
            conn.commit()

    def alter_role(self, role, password):
        with self.cursor() as (conn, cursor):
            cursor.execute("UPDATE roles SET password = ? WHERE role = ?", (password, role))
            conn.commit()

    def drop_role(self, role, with_databases=False):
        with self.cursor() as (conn, cursor):
            if with_databases:
                cursor.execute("DELETE FROM databases WHERE database IN (SELECT database FROM grants WHERE role = ?)", (role,))
            cursor.execute("DELETE FROM grants WHERE role = ?", (role,))
            cursor.execute("DELETE FROM roles WHERE role = ?", (role,))
            conn.commit()

    def grant(self, role, database, is_admin=None, alias=None):
        with self.cursor() as (conn, cursor):
            cursor.execute("""INSERT INTO grants (role, database, is_admin, alias) VALUES (?, ?, ?, ?)
                           ON CONFLICT (role, database) DO UPDATE SET is_admin = excluded.is_admin, alias = excluded.alias""", (role, database, is_admin, alias))
            conn.commit()

    def revoke(self, role, database):
        with self.cursor() as (conn, cursor):
            cursor.execute("DELETE FROM grants WHERE role = ? AND database = ?", (role, database))
            conn.commit()
        
    def get_databases_for_role(self, role):
        with self.cursor() as (conn, cursor):
            cursor.execute("SELECT database FROM grants WHERE role = ?", (role,))
            return [row[0] for row in cursor.fetchall()]

    def get_database_for_role(self, role, database):
        if role == "system":
            return self.get_database(database, ddl_allowed=True, role=role)
        if database == "system":
            return None
        with self.cursor() as (conn, cursor):
            cursor.execute("SELECT database, is_admin FROM grants WHERE role = ? AND (database = ? OR alias = ?)", (role, database, database))
            row = cursor.fetchone()
            if row is None:
                return None
            return self.get_database(row[0], ddl_allowed=row[1], role=role, cursor=cursor)
