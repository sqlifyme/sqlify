import json
import pytest
from sqlify.db import Database, DatabaseError, find_url_match, extract_auth, Credential


@pytest.fixture
def files_dir(tmp_path):
    (tmp_path / "users.csv").write_text("id,name\n1,alice\n2,bob\n")
    (tmp_path / "tables.json").write_text(json.dumps([{"name": "users", "label": "Users"}]))
    (tmp_path / "cols.json").write_text(json.dumps([{"name": "id"}, {"name": "name"}]))
    return tmp_path


@pytest.fixture
def db(files_dir):
    return Database(name="test", files_dir=str(files_dir))


SCHEMA_SQL = """CREATE SCHEMA WITH
    TABLES AS (SELECT * FROM "file://tables.json")
    COLUMNS AS (SELECT * FROM "file://cols.json")
    ROWS AS (SELECT * FROM "file://$TABLE[name].csv")"""


def rows(dt):
    return [tuple(r) for r in dt]


def test_find_url_match():
    data = {c.url: c for c in [
        Credential("a", "http://example.com", "type", "value"),
        Credential("b", "http://example.com/long/path", "type", "value"),
        Credential("c", "http://example.com/path", "type", "value"),
        Credential("d", "http://example.com/path/*/sub", "type", "value"),
        Credential("e", "http://example.com/other/*/sub/*/more", "type", "value"),
    ]}

    assert find_url_match(data, "http://example.com") == data["http://example.com"]
    assert find_url_match(data, "http://example.com/long/path") == data["http://example.com/long/path"]
    assert find_url_match(data, "http://example.com/long/path/more") == data["http://example.com/long/path"]
    assert find_url_match(data, "http://example.com/long/path/more/more/more/more/more/more/more") == data["http://example.com/long/path"]
    assert find_url_match(data, "http://example.com/path") == data["http://example.com/path"]
    assert find_url_match(data, "http://example.com/path/more") == data["http://example.com/path"]
    assert find_url_match(data, "http://example.com/path/hello/sub") == data["http://example.com/path/*/sub"]
    assert find_url_match(data, "http://example.com/path/hello/sub/sub") == data["http://example.com/path/*/sub"]
    assert find_url_match(data, "http://example.com/other/hello/sub/world/more") == data["http://example.com/other/*/sub/*/more"]
    assert find_url_match(data, "http://other.com") is None


def test_extract_auth():
    assert extract_auth("http://example.com/path") == (None, "http://example.com/path")
    assert extract_auth("http://user@example.com/path") == ("user", "http://example.com/path")
    assert extract_auth("http://user:pwd@example.com") == ("user:pwd", "http://example.com")


def test_select_from_file(db):
    dt = db.execute('SELECT * FROM "file://users.csv"')
    assert dt.colnames == ["id", "name"]
    assert rows(dt) == [(1, "alice"), (2, "bob")]

    dt = db.execute('SELECT name FROM "file://users.csv" WHERE id = 2')
    assert rows(dt) == [("bob",)]


def test_unknown_table(db):
    with pytest.raises(DatabaseError, match="Table or view nope not found"):
        db.execute("SELECT * FROM nope")


def test_explain(db):
    dt = db.execute('EXPLAIN SELECT * FROM "file://users.csv"')
    assert dt.colnames == ["EXPLAIN"]
    assert "Load" in rows(dt)[0][0]


def test_ddl_statements_return_ok(db):
    dt = db.execute('CREATE ALIAS users AS "file://users.csv"')
    assert dt.colnames == ["CREATE ALIAS"]
    assert rows(dt) == [("ok",)]


def test_alias(db):
    db.execute('CREATE ALIAS users AS "file://users.csv"')
    assert db.aliases == {"users": "file://users.csv"}
    assert rows(db.execute("SELECT name FROM users")) == [("alice",), ("bob",)]
    assert rows(db.execute("SHOW ALIASES")) == [("users", "file://users.csv")]

    db.execute("DROP ALIAS users")
    assert db.aliases == {}
    with pytest.raises(DatabaseError):
        db.execute("SELECT name FROM users")


def test_view(db):
    db.execute('CREATE ALIAS users AS "file://users.csv"')
    db.execute("CREATE VIEW first_user AS SELECT name FROM users WHERE id = 1")
    assert rows(db.execute("SELECT * FROM first_user")) == [("alice",)]
    assert rows(db.execute("SHOW VIEWS")) == [("first_user",)]
    assert "FROM \"users\"" in rows(db.execute("SHOW VIEW first_user"))[0][0]

    db.execute("DROP VIEW first_user")
    assert db.views == {}
    with pytest.raises(DatabaseError, match="View first_user not found"):
        db.execute("SHOW VIEW first_user")


def test_view_is_evaluated_lazily(db, files_dir):
    db.execute('CREATE VIEW v AS SELECT name FROM "file://users.csv"')
    (files_dir / "users.csv").write_text("id,name\n3,carol\n")
    assert rows(db.execute("SELECT * FROM v")) == [("carol",)]


def test_refresh_non_materialized_view(db):
    db.execute("CREATE VIEW v AS SELECT 1 AS x")
    with pytest.raises(DatabaseError, match="View is not materialized"):
        db.execute("REFRESH MATERIALIZED VIEW v")
    with pytest.raises(DatabaseError, match="View nope not found"):
        db.execute("REFRESH MATERIALIZED VIEW nope")


def test_materialized_view(db, files_dir):
    db.execute('CREATE MATERIALIZED VIEW mv AS SELECT name FROM "file://users.csv"')
    (files_dir / "users.csv").write_text("id,name\n3,carol\n")
    assert rows(db.execute("SELECT * FROM mv")) == [("alice",), ("bob",)]
    # cached rows can be read more than once
    assert rows(db.execute("SELECT * FROM mv")) == [("alice",), ("bob",)]
    assert db.get_view_columns("mv") == ["name"]

    db.execute("REFRESH MATERIALIZED VIEW mv")
    assert rows(db.execute("SELECT * FROM mv")) == [("carol",)]


def test_get_view_columns(db):
    db.execute("CREATE VIEW v AS SELECT 1 AS x")
    assert db.get_view_columns("v") == []


def test_scheme(db):
    db.execute('CREATE SCHEME data AS "file://$PATH"')
    assert rows(db.execute('SELECT name FROM "data://users.csv"')) == [("alice",), ("bob",)]
    assert rows(db.execute("SHOW SCHEMES")) == [("data", "file://$PATH")]

    db.execute("DROP SCHEME data")
    assert db.schemes == {}


def test_credentials(db):
    db.execute("CREATE CREDENTIALS ON http://example.com TOKEN tok")
    db.execute("CREATE CREDENTIALS named ON http://example.com/api AUTH user:pwd")

    assert db.get_credentials("http://example.com/foo").value == "tok"
    assert db.get_credentials("http://example.com/api/foo").name == "named"
    # credentials can be selected by name through the url auth part
    assert db.get_credentials("http://named@example.com/foo").name == "named"
    # explicit user:password in the url disables credentials lookup
    assert db.get_credentials("http://u:p@example.com/foo") is None
    assert db.get_credentials("http://other.com") is None

    # credential values are never shown
    assert rows(db.execute("SHOW CREDENTIALS")) == [
        ("http://example.com", "http://example.com", "token"),
        ("named", "http://example.com/api", "auth"),
    ]

    db.execute("DROP CREDENTIALS named")
    assert list(db.credentials) == ["http://example.com"]


def test_headers(db):
    db.execute("CREATE HEADER ON http://example.com AS 'X-A: 1'")
    db.execute("CREATE HEADER ON http://example.com AS 'X-B: 2'")
    assert db.get_headers("http://example.com/foo") == [("X-A", "1"), ("X-B", "2")]
    assert db.get_headers("http://other.com") == {}
    assert rows(db.execute("SHOW HEADERS")) == [
        ("http://example.com", "X-A", "1"),
        ("http://example.com", "X-B", "2"),
    ]

    db.execute("DROP HEADER http://example.com")
    assert db.headers == {}


def test_pagination(db):
    db.execute("CREATE PAGINATION ON http://example.com/api AS page=body(next)")
    pagination = db.get_pagination("http://user@example.com/api/items")
    assert (pagination.param, pagination.location, pagination.name) == ("page", "body", "next")
    assert db.get_pagination("http://other.com") is None
    assert rows(db.execute("SHOW PAGINATIONS")) == [("http://example.com/api", "page", "body", "next")]

    db.execute("DROP PAGINATION http://example.com/api")
    assert db.paginations == {}


def test_schema(db):
    db.execute(SCHEMA_SQL)
    assert db.tables == {
        "users": {"meta": {"name": "users", "label": "Users"}, "cols": [{"name": "id"}, {"name": "name"}]}
    }
    assert rows(db.execute("SELECT name FROM users WHERE id = 2")) == [("bob",)]
    assert rows(db.execute("SHOW TABLES")) == [("users",)]

    dt = db.execute("SHOW TABLE users")
    assert dt.colnames == ["name"]
    assert rows(dt) == [("id",), ("name",)]

    dt = db.execute("SHOW SCHEMA")
    assert rows(dt)[0][0] == 'SELECT * FROM "file://tables.json"'

    with pytest.raises(DatabaseError, match="Table nope not found"):
        db.execute("SHOW TABLE nope")


def test_schema_without_columns(db):
    db.execute('CREATE SCHEMA WITH TABLES AS (SELECT * FROM "file://tables.json") '
               'ROWS AS (SELECT * FROM "file://$TABLE[name].csv")')
    assert db.tables["users"]["cols"] == []
    assert rows(db.execute("SELECT name FROM users WHERE id = 1")) == [("alice",)]


def test_refresh_schema(db, files_dir):
    with pytest.raises(DatabaseError, match="No schema defined"):
        db.execute("REFRESH SCHEMA")

    db.execute(SCHEMA_SQL)
    (files_dir / "tables.json").write_text(json.dumps([{"name": "users"}, {"name": "groups"}]))
    db.execute("REFRESH SCHEMA")
    assert set(db.tables) == {"users", "groups"}


def test_schema_refresh_failure(db):
    with pytest.raises(DatabaseError, match="Failed refreshing schema"):
        db.execute('CREATE SCHEMA WITH TABLES AS (SELECT * FROM "file://missing.json") ROWS AS (SELECT 1)')


def test_drop_schema(db):
    db.execute(SCHEMA_SQL)
    db.execute("DROP SCHEMA")
    assert db.schema is None


def test_table_takes_precedence_over_view(db):
    db.execute(SCHEMA_SQL)
    db.execute("CREATE VIEW users AS SELECT 'view' AS name")
    assert rows(db.execute("SELECT name FROM users WHERE id = 1")) == [("alice",)]


def test_show_server_config(db):
    assert rows(db.execute("SHOW transaction isolation level")) == [("read committed",)]
    assert rows(db.execute("SHOW standard_conforming_strings")) == [("on",)]
    with pytest.raises(DatabaseError, match="Unknown show type"):
        db.execute("SHOW nope")


def test_information_schema(db):
    db.execute(SCHEMA_SQL)
    db.execute("CREATE VIEW v AS SELECT 1 AS x")

    dt = db.execute("SELECT table_name, table_type FROM information_schema.tables")
    assert rows(dt) == [("users", "BASE TABLE"), ("v", "VIEW")]

    dt = db.execute("SELECT table_name, view_definition FROM information_schema.views")
    assert rows(dt) == [("v", 'SELECT 1 AS "x"')]

    dt = db.execute("SELECT table_name, column_name, ordinal_position FROM information_schema.columns")
    assert rows(dt) == [("users", "id", 0), ("users", "name", 1)]


def test_ddl_not_allowed(files_dir):
    db = Database(files_dir=str(files_dir), ddl_allowed=False)
    for sql in [
        "CREATE ALIAS a AS b",
        "DROP ALIAS a",
        'CREATE SCHEME data AS "file://$PATH"',
        "DROP SCHEME data",
        "CREATE VIEW v AS SELECT 1",
        "DROP VIEW v",
        "CREATE CREDENTIALS ON http://example.com TOKEN tok",
        "CREATE HEADER ON http://example.com AS 'X-A: 1'",
        "CREATE PAGINATION ON http://example.com AS page=body(next)",
        SCHEMA_SQL,
        "DROP SCHEMA",
    ]:
        with pytest.raises(DatabaseError, match="DDL not allowed"):
            db.execute(sql)
    assert db.aliases == {} and db.schemes == {}
    assert db.views == {} and db.credentials == {} and db.schema is None

    # selects are always allowed
    assert rows(db.execute('SELECT name FROM "file://users.csv" WHERE id = 1')) == [("alice",)]


def test_ddl_callback(files_dir):
    calls = []
    db = Database(files_dir=str(files_dir), ddl_callback=calls.append)
    db.execute("CREATE ALIAS a AS b")
    db.execute("CREATE VIEW v AS SELECT 1 AS x")
    db.execute("DROP ALIAS a")
    assert calls == [db, db, db]
    db.execute("SELECT 1 AS x")
    assert len(calls) == 3


def test_config_roundtrip(db):
    db.execute('CREATE ALIAS users AS "file://users.csv"')
    db.execute("CREATE VIEW first_user AS SELECT name FROM users WHERE id = 1")
    db.execute('CREATE SCHEME data AS "file://$PATH"')
    db.execute("CREATE CREDENTIALS ON http://example.com TOKEN tok")
    db.execute("CREATE PAGINATION ON http://example.com AS page=body(next)")
    db.execute("CREATE HEADER ON http://example.com AS 'X-A: 1'")
    db.execute(SCHEMA_SQL)

    # the config must be serializable as json
    config = json.loads(json.dumps(db.as_config()))
    db2 = Database.from_config(config, files_dir=db.files_dir)

    assert db2.aliases == db.aliases
    assert db2.schemes == db.schemes
    assert db2.credentials == db.credentials
    assert db2.paginations == db.paginations
    assert db2.schema == db.schema
    assert db2.tables == db.tables
    assert rows(db2.execute("SELECT * FROM first_user")) == [("alice",)]
    assert rows(db2.execute('SELECT name FROM "data://users.csv" WHERE id = 2')) == [("bob",)]


def test_from_uri(files_dir):
    assert Database.from_uri(":memory:").views == {}

    config_file = files_dir / "db.json"
    config_file.write_text("{}")
    db = Database.from_uri(str(config_file), files_dir=str(files_dir))
    db.execute('CREATE ALIAS users AS "file://users.csv"')
    db.execute("CREATE VIEW first_user AS SELECT name FROM users WHERE id = 1")

    # DDL changes are persisted to the config file
    db2 = Database.from_uri(str(config_file), files_dir=str(files_dir))
    assert db2.aliases == {"users": "file://users.csv"}
    assert rows(db2.execute("SELECT * FROM first_user")) == [("alice",)]
