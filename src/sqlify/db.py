from sqletl.planner import plan
from sqletl.datatable import DataTable, DictDataTable
from sqletl.pipeline import Pipeline
from dataclasses import dataclass
from dataclasses_json import dataclass_json
import json
import os
import functools
import pickle
import codecs
import re
from .ctx import Context
from .parser import parse
from . import ast


class DatabaseError(Exception):
    pass


def node_handler(node_class, callback=None):
    def decorator(func):
        def cmd(self, node):
            args = tuple()
            if callback:
                args = callback(node)
            rv = func(self, *args)
            if isinstance(rv, DataTable):
                return rv
            return DictDataTable([{func.__name__.replace('_', ' ').upper(): "ok"}])
        func.__node_handler__ = (node_class, cmd)
        return func
    return decorator


def ddl_only(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.ddl_allowed:
            raise DatabaseError("DDL not allowed")
        return func(self, *args, **kwargs)
    return wrapper


@dataclass
class View:
    name: str
    query: str
    pipeline: Pipeline
    materialized: bool
    columns: str | list

    @classmethod
    def from_dict(cls, d):
        return cls(d["name"], d["query"], pickle.loads(codecs.decode(d["pipeline"].encode(), "base64")), d["materialized"], d["columns"])

    def to_dict(self):
        return {
            "name": self.name,
            "query": self.query,
            "pipeline": codecs.encode(pickle.dumps(self.pipeline), "base64").decode(),
            "materialized": self.materialized,
            "columns": self.columns
        }
    

@dataclass_json
@dataclass
class Scheme:
    name: str
    uri_template: str


@dataclass_json
@dataclass
class Pagination:
    url: str
    param: str
    location: str
    name: str


@dataclass_json
@dataclass
class Credential:
    name: str
    url: str
    type: str
    value: str


@dataclass_json
@dataclass
class Schema:
    tables: str
    columns: str
    rows: str


class Database:
    @classmethod
    def from_uri(cls, uri, **kwargs):
        if uri == ":memory:":
            return cls(**kwargs)
        
        with open(uri) as f:
            config = json.load(f)

        def ddl_callback(db):
            with open(uri, "w") as f:
                json.dump(db.as_config(), f)

        kwargs["ddl_callback"] = ddl_callback
        return cls.from_config(config, **kwargs)

    @classmethod
    def from_config(cls, config, **kwargs):
        db = cls(**kwargs)
        db.aliases = config.get("aliases", {})
        db.views = {v["name"]: View.from_dict(v) for v in config.get("views", [])}
        db.schemes = config.get("schemes", {})
        db.credentials = {v["name"]: Credential.from_dict(v) for v in config.get("credentials", [])}
        db.paginations = {v["url"]: Pagination.from_dict(v) for v in config.get("paginations", [])}
        db.headers = config.get("headers", {})
        db.schema = Schema.from_dict(config["schema"]) if config.get("schema") else None
        db.tables = config.get("tables", {})
        return db
    
    def __init__(self, name=None, cache=None, files_dir=None, ddl_allowed=True, ddl_callback=None):
        self.name = name
        self.aliases = {}
        self.views = {}
        self.schemes = {}
        self.credentials = {}
        self.paginations = {}
        self.headers = {}
        self.schema = None
        self.tables = {}

        self.ddl_allowed = ddl_allowed
        if not ddl_callback:
            ddl_callback = lambda s: None
        self.ddl_callback = ddl_callback

        self.files_dir = files_dir if files_dir else os.getcwd()

        if cache:
            self.cache = cache
        elif not hasattr(self, "cache"):
            self.cache = Cache()

        self.node_handlers = {}
        for name in dir(self):
            attr = getattr(self, name)
            if hasattr(attr, "__node_handler__"):
                node_class, cmd = attr.__node_handler__
                self.node_handlers[node_class] = cmd

    def execute(self, query: ast.Node | str) -> DataTable:
        if isinstance(query, str):
            query = parse(query)
        if query.__class__ in self.node_handlers:
            return self.node_handlers[query.__class__](self, query)
        if isinstance(query, ast.Explain):
            return DictDataTable([{"EXPLAIN": repr(plan(query.select))}])
        return self.execute_select(query)
        
    def execute_select(self, query: ast.Node | str, params = None) -> DataTable:
        if isinstance(query, str):
            query = parse(query)
        pipe = plan(query)
        return pipe.run(self.create_context(params))
    
    def create_context(self, params=None) -> Context:
        return Context(self, params)
    
    def pipeline(self, query) -> Pipeline:
        if isinstance(query, str):
            query = parse(query)
        return plan(query)
    
    @node_handler(ast.CreateAlias, lambda node: (node.name, node.replace_with))
    @ddl_only
    def create_alias(self, name, replace_with):
        self.aliases[name] = replace_with
        self.ddl_callback(self)

    @node_handler(ast.DropAlias, lambda node: (node.name,))
    @ddl_only
    def drop_alias(self, name):
        self.aliases.pop(name, None)
        self.ddl_callback(self)

    @node_handler(ast.CreateView, lambda node: (node.name, node.select, node.materialized))
    @ddl_only
    def create_view(self, name, query, materialized=False, columns=None) -> View:
        pipe = plan(query)
        self.views[name] = View(name, str(query), pipe, materialized, columns)
        self.ddl_callback(self)
        if materialized:
            self.refresh_materialized_view(name)
        return self.views[name]
    
    def _view_cache_key_cols(self, name):
        return f"view:{name}:cols"
    
    def _view_cache_key_rows(self, name):
        return f"view:{name}:rows"

    def get_view(self, name) -> View:
        if name not in self.views:
            raise DatabaseError(f"View {name} not found")
        return self.views[name]
    
    def get_view_columns(self, name):
        view = self.get_view(name)
        if view.materialized:
            return self.cache.get(self._view_cache_key_cols(view.name))
        if isinstance(view.columns, str):
            return [r[0] for r in self.execute(view.columns)]
        if not view.columns:
            return []
        return view.columns
    
    def fetch_view(self, name, params=None, ctx=None):
        view = self.get_view(name)
        if view.materialized:
            cols = self.cache.get(self._view_cache_key_cols(view.name))
            rows = self.cache.get(self._view_cache_key_rows(view.name))
            return DataTable(cols, rows)
        return view.pipeline.run(self.create_context(params))
    
    @node_handler(ast.RefreshMaterializedView, lambda node: (node.name,))
    @ddl_only
    def refresh_materialized_view(self, name):
        view = self.get_view(name)
        if not view.materialized:
            raise DatabaseError("View is not materialized")
        dt = view.pipeline.run(self.create_context())
        self.cache.set(self._view_cache_key_cols(name), dt.colnames)
        self.cache.set(self._view_cache_key_rows(name), list(dt.rows))

    @node_handler(ast.DropView, lambda node: (node.name,))
    @ddl_only
    def drop_view(self, name):
        self.views.pop(name, None)
        self.ddl_callback(self)

    @node_handler(ast.CreateScheme, lambda node: (node.scheme, node.uri_template))
    @ddl_only
    def create_scheme(self, scheme, uri_template):
        self.schemes[scheme] = uri_template
        self.ddl_callback(self)

    @node_handler(ast.DropScheme, lambda node: (node.scheme,))
    @ddl_only
    def drop_scheme(self, scheme):
        self.schemes.pop(scheme, None)
        self.ddl_callback(self)

    @node_handler(ast.CreatePagination, lambda node: (node.url, node.param, node.location, node.name))
    @ddl_only
    def create_pagination(self, url, param, location, name):
        self.paginations[url] = Pagination(url, param, location, name)
        self.ddl_callback(self)

    def get_pagination(self, url):
        _, url = extract_auth(url)
        return find_url_match(self.paginations, url)

    @node_handler(ast.DropPagination, lambda node: (node.url,))
    @ddl_only
    def drop_pagination(self, url):
        self.paginations.pop(url, None)
        self.ddl_callback(self)

    @node_handler(ast.CreateCredentials, lambda node: (node.name, node.url, node.type, node.value))
    @ddl_only
    def create_credentials(self, name, url, type, value):
        self.credentials[name] = Credential(name, url, type, value)
        self.ddl_callback(self)

    def get_credentials(self, url):
        auth, url = extract_auth(url)
        if auth and ":" not in auth:
            return self.credentials.get(auth)
        if auth:
            return
        return find_url_match({i.url: i for i in reversed(self.credentials.values())}, url)

    @node_handler(ast.DropCredentials, lambda node: (node.name,))
    @ddl_only
    def drop_credentials(self, name):
        self.credentials.pop(name, None)
        self.ddl_callback(self)

    @node_handler(ast.CreateHeader, lambda node: (node.url, node.name, node.value))
    @ddl_only
    def create_header(self, url, name, value):
        self.headers.setdefault(url, []).append((name, value))
        self.ddl_callback(self)

    def get_headers(self, url):
        auth, url = extract_auth(url)
        return find_url_match(self.headers, url) or {}

    @node_handler(ast.DropHeader, lambda node: (node.url,))
    @ddl_only
    def drop_headers(self, url):
        self.headers.pop(url, None)
        self.ddl_callback(self)

    @node_handler(ast.CreateSchema, lambda node: (node.tables, node.columns, node.rows))
    @ddl_only
    def create_schema(self, tables, columns, rows):
        self.schema = Schema(tables, columns, rows)
        self.ddl_callback(self)
        self.refresh_schema()

    @node_handler(ast.RefreshSchema)
    @ddl_only
    def refresh_schema(self):
        if not self.schema:
            raise DatabaseError("No schema defined")
        try:
            tables = self.execute_select(self.schema.tables)
        except:
            raise DatabaseError("Failed refreshing schema (tables)")
        for table in tables.to_dict():
            if not self.schema.columns:
                self.tables[table["name"]] = {"meta": table, "cols": []}
                continue
            stmt = self.schema.columns
            for col, value in table.items():
                stmt = stmt.replace(f"$TABLE[{col}]", str(value))
            try:
                cols = self.execute_select(stmt).to_dict()
            except:
                raise DatabaseError("Failed refreshing schema (columns)")
            self.tables[table["name"]] = {"meta": table, "cols": cols}
        self.ddl_callback(self)

    @node_handler(ast.DropSchema)
    @ddl_only
    def drop_schema(self):
        self.schema = None
        self.ddl_callback(self)

    def fetch_table(self, name, params=None, ctx=None):
        if name not in self.tables:
            raise DatabaseError(f"Table {name} not found")
        stmt = self.schema.rows
        for col, value in self.tables[name]["meta"].items():
            stmt = stmt.replace(f"$TABLE[{col}]", str(value))
        return self.execute_select(stmt, params)
    
    def fetch(self, table_or_view, params=None, ctx=None):
        if table_or_view in self.tables:
            return self.fetch_table(table_or_view, params, ctx)
        if table_or_view in self.views:
            return self.fetch_view(table_or_view, params, ctx)
        raise DatabaseError(f"Table or view {table_or_view} not found")
    
    @node_handler(ast.Show, lambda node: (node.type, node.name))
    def show(self, type, name=None):
        if type == "tables":
            return DataTable(["name"], [[name] for name in self.tables])
        if type == "table":
            if name not in self.tables:
                raise DatabaseError(f"Table {name} not found")
            cols = list(self.tables[name]["cols"])
            if not cols:
                return DataTable()
            cols = [c for c in cols[0].keys() if c != "name"]
            return DictDataTable(self.tables[name]["cols"], ["name"] + cols)
        if type == "views":
            return DataTable(["name"], [[name] for name in self.views])
        if type == "view":
            if name not in self.views:
                raise DatabaseError(f"View {name} not found")
            return DataTable(["query"], [[self.views[name].query]])
        if type == "aliases":
            return DataTable(["alias", "replace_with"], [(alias, replace_with) for alias, replace_with in self.aliases.items()])
        if type == "schemes":
            return DataTable(["scheme", "uri_template"], [(scheme, uri_template) for scheme, uri_template in self.schemes.items()])
        if type == "schema":
            return DictDataTable([self.schema.to_dict()])
        if type == "credentials":
            return DataTable(["name", "url", "type"], [(c.name, c.url, c.type) for c in self.credentials.values()])
        if type == "paginations":
            return DictDataTable([p.to_dict() for p in self.paginations.values()])
        if type == "headers":
            return DataTable(["url", "name", "value"], [(url, name, value) for url, headers in self.headers.items() for name, value in headers])
        server_config_key = (f"{type} {name}" if name else type).lower()
        if server_config_key in POSTGRESQL_SERVER_CONFIG:
            return DictDataTable([POSTGRESQL_SERVER_CONFIG[server_config_key]])
        raise DatabaseError(f"Unknown show type {type}")
    
    def get_information_schema_db(self):
        return InformationSchemaDatabase(self)

    def as_config(self):
        return {
            "aliases": self.aliases,
            "views": [v.to_dict() for v in self.views.values()],
            "schemes": self.schemes,
            "credentials": [v.to_dict() for v in self.credentials.values()],
            "paginations": [v.to_dict() for v in self.paginations.values()],
            "headers": self.headers,
            "schema": self.schema.to_dict() if self.schema else None,
            "tables": self.tables
        }


class InformationSchemaDatabase(Database):
    def __init__(self, db, **kwargs):
        super().__init__(name="information_schema", **kwargs)
        self.db = db

    def fetch(self, table_or_view, params=None, ctx=None):
        if table_or_view.lower() == "tables":
            return DictDataTable([
                {
                    "table_catalog": self.db.name,
                    "table_schema": "public",
                    "table_name": n,
                    "table_type": "BASE TABLE",
                    "self_referencing_column_name": None,
                    "reference_generation": None,
                    "user_defined_type_catalog": None,
                    "user_defined_type_schema": None,
                    "user_defined_type_name": None,
                    "is_insertable_into": "NO",
                    "is_typed": "NO",
                    "commit_action": ""
                }
                for n, t in self.db.tables.items()
            ] + [
                {
                    "table_catalog": self.db.name,
                    "table_schema": "public",
                    "table_name": n,
                    "table_type": "VIEW",
                    "self_referencing_column_name": None,
                    "reference_generation": None,
                    "user_defined_type_catalog": None,
                    "user_defined_type_schema": None,
                    "user_defined_type_name": None,
                    "is_insertable_into": "NO",
                    "is_typed": "NO",
                    "commit_action": ""
                }
                for n, v in self.db.views.items()
            ])
        if table_or_view.lower() == "views":
            return DictDataTable([
                {
                    "table_catalog": self.db.name,
                    "table_schema": "public",
                    "table_name": n,
                    "view_definition": v.query,
                    "check_option": "NONE",
                    "is_updatable": "NO",
                    "is_insertable_into": "NO",
                    "is_trigger_updatable": "NO",
                    "is_trigger_deletable": "NO",
                    "is_trigger_insertable_into": "NO"
                }
                for n, v in self.db.views.items()
            ])
        if table_or_view.lower() == "columns":
            return DictDataTable([
                {
                    "table_catalog": self.db.name,
                    "table_schema": "public",
                    "table_name": table,
                    "column_name": col["name"],
                    "ordinal_position": i,
                    "column_default": None,
                    "is_nullable": "YES",
                    "data_type": "text",
                    "character_maximum_length": None,
                    "character_octet_length": None,
                    "numeric_precision": None,
                    "numeric_precision_radix": None,
                    "numeric_scale": None,
                    "datetime_precision": None,
                    "interval_type": None,
                    "interval_precision": None,
                    "character_set_catalog": None,
                    "character_set_schema": None,
                    "character_set_name": None,
                    "collation_catalog": None,
                    "collation_schema": None,
                    "collation_name": None,
                    "domain_catalog": None,
                    "domain_schema": None,
                    "domain_name": None,
                    "udt_catalog": None,
                    "udt_schema": None,
                    "udt_name": None,
                    "scope_catalog": None,
                    "scope_schema": None,
                    "scope_name": None,
                    "maximum_cardinality": None,
                    "dtd_identifier": None,
                    "is_self_referencing": "NO",
                    "is_identity": "NO",
                    "identity_generation": None,
                    "identity_start": None,
                    "identity_increment": None,
                    "identity_maximum": None,
                    "identity_minimum": None,
                    "identity_cycle": "NO",
                    "is_generated": "NEVER",
                    "generation_expression": None,
                    "is_updatable": "NO"
                }
                for table, t in self.db.tables.items()
                for i, col in enumerate(t["cols"])
            ])
        return DataTable()


class Cache:
    def __init__(self):
        self.cache = {}

    def get(self, key):
        return self.cache.get(key)

    def set(self, key, value):
        self.cache[key] = value



def extract_auth(url):
    if "@" in url:
        scheme, url = url.split("://", 1)
        auth, url = url.split("@")
        return auth, f"{scheme}://{url}"
    return None, url


def find_url_match(urls, url):
    matches = {}
    for cred_url in urls.keys():
        if "*" in cred_url and re.match(cred_url.replace("/*/", "/.*/"), url) or url.startswith(cred_url):
            matches[cred_url] = abs(len(cred_url) - len(url))
    if matches:
        matches = sorted(matches.items(), key=lambda x: x[1])
        return urls[matches[0][0]]
    

POSTGRESQL_SERVER_CONFIG = {
    "transaction isolation level": {"transaction_isolation": "read committed"},
    "standard_conforming_strings": {"standard_conforming_strings": "on"}
}