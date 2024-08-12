from sqletl.ast import *


class Explain(Node):
    def __init__(self, select):
        self.select = select


class CreateAlias(Node):
    def __init__(self, name, replace_with):
        self.name = name
        self.replace_with = replace_with


class DropAlias(Node):
    def __init__(self, name):
        self.name = name


class CreateView(Node):
    def __init__(self, name, select, materialized=False):
        self.name = name
        self.select = select
        self.materialized = materialized


class RefreshMaterializedView(Node):
    def __init__(self, name):
        self.name = name


class DropView(Node):
    def __init__(self, name):
        self.name = name


class CreateScheme(Node):
    def __init__(self, scheme, uri_template):
        self.scheme = scheme.lower()
        self.uri_template = uri_template


class DropScheme(Node):
    def __init__(self, scheme):
        self.scheme = scheme


class CreateCredentials(Node):
    def __init__(self, url, type, value, name=None):
        self.url = url
        self.type = type
        self.value = value
        self.name = name or url


class DropCredentials(Node):
    def __init__(self, name):
        self.name = name


class CreatePagination(Node):
    def __init__(self, url, param, location, name):
        self.url = url
        self.param = param
        self.location = location
        self.name = name


class DropPagination(Node):
    def __init__(self, url):
        self.url = url


class CreateHeader(Node):
    def __init__(self, url, name, value):
        self.url = url
        self.name = name
        self.value = value


class DropHeader(Node):
    def __init__(self, url):
        self.url = url


class CreateDatabase(Node):
    def __init__(self, name):
        self.name = name


class DropDatabase(Node):
    def __init__(self, name):
        self.name = name


class CreateSchema(Node):
    def __init__(self, tables, rows, columns=None):
        self.tables = tables
        self.rows = rows
        self.columns = columns


class RefreshSchema(Node):
    pass


class DropSchema(Node):
    pass


class CreateRole(Node):
    def __init__(self, role, password=None):
        self.role = role
        self.password = password


class AlterRole(Node):
    def __init__(self, role, password=None):
        self.role = role
        self.password = password


class DropRole(Node):
    def __init__(self, role, with_databases=False):
        self.role = role
        self.with_databases = with_databases


class Grant(Node):
    def __init__(self, role, database, is_admin=False, alias=None):
        self.role = role
        self.database = database
        self.is_admin = is_admin
        self.alias = alias


class Revoke(Node):
    def __init__(self, role, database):
        self.role = role
        self.database = database


class Show(Node):
    def __init__(self, type, name=None):
        self.type = type
        self.name = name