from sqlify.ast import *
from sqlify.parser import parse


def test_explain():
    sql = "EXPLAIN SELECT * FROM my_table"
    assert parse(sql) == Explain(Select([], [Table("my_table")]))


def test_create_alias():
    sql = "CREATE ALIAS my_alias AS my_table"
    assert parse(sql) == CreateAlias("my_alias", "my_table")

    sql = 'CREATE ALIAS my_alias AS "http://example.com#hello"'
    assert parse(sql) == CreateAlias("my_alias", "http://example.com#hello")


def test_drop_alias():
    sql = "DROP ALIAS my_alias"
    assert parse(sql) == DropAlias("my_alias")


def test_create_view():
    sql = "CREATE VIEW my_view AS SELECT * FROM my_table"
    assert parse(sql) == CreateView("my_view", Select([], [Table("my_table")]))

    sql = "CREATE MATERIALIZED VIEW my_view AS SELECT * FROM my_table"
    assert parse(sql) == CreateView("my_view", Select([], [Table("my_table")]), True)


def text_refresh_materialized_view():
    sql = "REFRESH MATERIALIZED VIEW my_view"
    assert parse(sql) == RefreshMaterializedView("my_view")


def test_drop_view():
    sql = "DROP VIEW my_view"
    assert parse(sql) == DropView("my_view")


def test_create_scheme():
    sql = 'CREATE SCHEME my_scheme AS "http://example.com/$PATH"'
    assert parse(sql) == CreateScheme("my_scheme", "http://example.com/$PATH")


def test_drop_scheme():
    sql = "DROP SCHEME my_scheme"
    assert parse(sql) == DropScheme("my_scheme")


def test_create_credentials():
    sql = "CREATE CREDENTIALS ON http://example.com TOKEN my_token"
    assert parse(sql) == CreateCredentials("http://example.com", "token", "my_token", None)

    sql = "CREATE CREDENTIALS my_creds ON http://example.com TOKEN my_token"
    assert parse(sql) == CreateCredentials("http://example.com", "token", "my_token", "my_creds")

    sql = "CREATE CREDENTIALS ON http://example.com AUTH user:password"
    assert parse(sql) == CreateCredentials("http://example.com", "auth", "user:password", None)


def test_drop_credentials():
    sql = "DROP CREDENTIALS http://example.com"
    assert parse(sql) == DropCredentials("http://example.com")

    sql = "DROP CREDENTIALS my_creds"
    assert parse(sql) == DropCredentials("my_creds")


def test_create_pagination():
    sql = "CREATE PAGINATION ON http://example.com AS page=body(next_page)"
    assert parse(sql) == CreatePagination("http://example.com", "page", "body", "next_page")

    sql = "CREATE PAGINATION ON http://example.com AS page=header(X-Next-Page)"
    assert parse(sql) == CreatePagination("http://example.com", "page", "header", "X-Next-Page")


def test_drop_pagination():
    sql = "DROP PAGINATION http://example.com"
    assert parse(sql) == DropPagination("http://example.com")


def test_create_database():
    sql = "CREATE DATABASE my_database"
    assert parse(sql) == CreateDatabase("my_database")


def test_drop_database():
    sql = "DROP DATABASE my_database"
    assert parse(sql) == DropDatabase("my_database")


def test_create_schema():
    sql = 'CREATE SCHEMA WITH TABLES AS (SELECT * FROM my_table) COLUMNS AS (SELECT * FROM my_cols) ROWS AS (SELECT * FROM my_rows)'
    assert parse(sql) == CreateSchema(tables="SELECT * FROM my_table", columns="SELECT * FROM my_cols", rows="SELECT * FROM my_rows")


def test_refresh_schema():
    sql = "REFRESH SCHEMA"
    assert parse(sql) == RefreshSchema()


def test_drop_schema():
    sql = "DROP SCHEMA"
    assert parse(sql) == DropSchema()


def test_create_role():
    sql = "CREATE ROLE my_user PASSWORD my_password"
    assert parse(sql) == CreateRole("my_user", "my_password")

    sql = "CREATE ROLE my_user"
    assert parse(sql) == CreateRole("my_user")


def test_drop_role():
    sql = "DROP ROLE my_user"
    assert parse(sql) == DropRole("my_user")


def test_grant():
    sql = "GRANT ON my_database TO my_user"
    assert parse(sql) == Grant("my_user", "my_database")

    sql = "GRANT ADMIN ON my_database TO my_user"
    assert parse(sql) == Grant("my_user", "my_database", True)


def test_revoke():
    sql = "REVOKE ON my_database FROM my_user"
    assert parse(sql) == Revoke("my_user", "my_database")