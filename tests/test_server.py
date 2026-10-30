import pytest
from sqlify.server import Server, ServerDatabase, AuthenticatedDatabase, SystemDatabase
from sqlify.db import DatabaseError


@pytest.fixture
def server(tmp_path):
    return Server(str(tmp_path / "sqlify.db"), files_dir=str(tmp_path / "files"), system_pwd="sys")


@pytest.fixture
def alice(server):
    """A role alice with read access to db1."""
    server.execute("system", "system", "CREATE DATABASE db1")
    server.execute("system", "system", "CREATE ROLE alice PASSWORD secret")
    server.execute("system", "system", "GRANT ON db1 TO alice AS mydb")
    return "alice"


def rows(dt):
    return [tuple(r) for r in dt]


def test_init(tmp_path, monkeypatch):
    server = Server(str(tmp_path / "sqlify.db"))
    assert (tmp_path / "sqlify.db").exists()
    assert server.files_dir == str(tmp_path / "user_files")
    assert server.get_databases() == []

    monkeypatch.setenv("SQLIFY_SYSTEM_PWD", "from_env")
    # reopening an existing server must not recreate the schema
    assert Server(str(tmp_path / "sqlify.db")).system_pwd == "from_env"


def test_system_authentication(server, tmp_path):
    assert server.authenticate("system", "sys", "anything")
    assert not server.authenticate("system", "wrong", "anything")
    assert not Server(str(tmp_path / "nopwd.db")).authenticate("system", None, "anything")


def test_role_authentication(server, alice):
    assert server.authenticate("alice", "secret", "db1")
    assert server.authenticate("alice", "secret", "mydb")
    assert not server.authenticate("alice", "wrong", "db1")
    assert not server.authenticate("alice", "secret", "other")
    assert not server.authenticate("bob", "secret", "db1")


def test_role_without_password_cannot_authenticate(server):
    server.create_database("db1")
    server.create_role("bob")
    server.grant("bob", "db1")
    assert not server.authenticate("bob", None, "db1")


def test_alter_role(server, alice):
    server.execute("system", "system", "ALTER ROLE alice PASSWORD other")
    assert not server.authenticate("alice", "secret", "db1")
    assert server.authenticate("alice", "other", "db1")

    server.execute("system", "system", "ALTER ROLE alice PASSWORD NULL")
    assert not server.authenticate("alice", None, "db1")


def test_databases(server):
    server.execute("system", "system", "CREATE DATABASE db1")
    server.execute("system", "system", "CREATE DATABASE db2")
    assert server.get_databases() == ["db1", "db2"]
    assert rows(server.execute("db1", "system", "SHOW DATABASES")) == [("db1",), ("db2",)]

    server.execute("system", "system", "DROP DATABASE db1")
    assert server.get_databases() == ["db2"]
    assert server.get_database("db1") is None


def test_get_database(server, alice):
    assert isinstance(server.get_database("system"), SystemDatabase)

    db = server.get_database("db1")
    assert type(db) is ServerDatabase
    assert db.name == "db1"
    assert not db.ddl_allowed
    assert db.files_dir == str(server.files_dir) + "/db1"

    assert type(server.get_database("db1", role="alice")) is AuthenticatedDatabase


def test_grant_and_revoke(server, alice):
    assert server.get_databases_for_role("alice") == ["db1"]
    assert rows(server.execute("db1", "alice", "SHOW DATABASES")) == [("db1",)]

    # databases can be accessed by their name or their alias
    assert server.get_database_for_role("alice", "db1").name == "db1"
    assert server.get_database_for_role("alice", "mydb").name == "db1"

    server.execute("system", "system", "REVOKE ON db1 FROM alice")
    assert server.get_databases_for_role("alice") == []
    assert server.get_database_for_role("alice", "db1") is None
    with pytest.raises(Exception, match="Role alice has no access to database db1"):
        server.execute("db1", "alice", "SHOW VIEWS")


def test_no_access(server, alice):
    server.create_database("db2")
    with pytest.raises(Exception, match="no access"):
        server.execute("db2", "alice", "SHOW VIEWS")
    with pytest.raises(Exception, match="no access"):
        server.execute("db1", "bob", "SHOW VIEWS")
    # only the system role can access the system database
    with pytest.raises(Exception, match="no access"):
        server.execute("system", "alice", "SHOW DATABASES")


def test_non_admin_cannot_run_ddl(server, alice):
    assert not server.get_database_for_role("alice", "db1").ddl_allowed
    for sql in ["CREATE VIEW v AS SELECT 1 AS x", "CREATE ALIAS a AS b", 'CREATE SCHEME data AS "file://$PATH"']:
        with pytest.raises(DatabaseError, match="DDL not allowed"):
            server.execute("db1", "alice", sql)
    db = server.get_database("db1")
    assert db.views == {} and db.aliases == {} and db.schemes == {}


def test_admin_can_run_ddl(server, alice):
    server.execute("system", "system", "GRANT ADMIN ON db1 TO alice")
    assert server.get_database_for_role("alice", "db1").ddl_allowed
    server.execute("db1", "alice", "CREATE VIEW v AS SELECT 1 AS x")
    assert rows(server.execute("db1", "alice", "SELECT * FROM v")) == [(1,)]


def test_system_can_run_ddl_on_any_database(server, alice):
    server.execute("db1", "system", "CREATE VIEW v AS SELECT 1 AS x")
    assert rows(server.execute("db1", "alice", "SELECT * FROM v")) == [(1,)]


def test_ddl_is_persisted(server, alice):
    server.execute("db1", "system", 'CREATE ALIAS a AS "file://a.csv"')
    server.execute("db1", "system", "CREATE VIEW v AS SELECT 1 AS x")

    # a fresh server instance reads the config from sqlite
    server2 = Server(server.sqlite_uri, files_dir=server.files_dir)
    db = server2.get_database("db1")
    assert db.aliases == {"a": "file://a.csv"}
    assert rows(db.execute("SELECT * FROM v")) == [(1,)]


def test_database_management_only_from_system(server, alice):
    server.execute("system", "system", "GRANT ADMIN ON db1 TO alice")
    with pytest.raises(Exception):
        server.execute("db1", "alice", "CREATE DATABASE db2")
    assert server.get_databases() == ["db1"]


def test_files_are_scoped_per_database(server, alice, tmp_path):
    (tmp_path / "files" / "db1").mkdir(parents=True)
    (tmp_path / "files" / "db1" / "users.csv").write_text("id,name\n1,alice\n")
    (tmp_path / "secret.csv").write_text("id\n1\n")

    assert rows(server.execute("db1", "alice", 'SELECT name FROM "file://users.csv"')) == [("alice",)]
    with pytest.raises(Exception):
        server.execute("db1", "alice", 'SELECT * FROM "file://../../secret.csv"')


def test_cross_database_query(server, alice):
    server.execute("system", "system", "CREATE DATABASE db2")
    server.execute("system", "system", "GRANT ON db2 TO alice")
    server.execute("db2", "system", "CREATE VIEW v AS SELECT 'from db2' AS x")
    assert rows(server.execute("db1", "alice", "SELECT x FROM db2.v")) == [("from db2",)]

    server.execute("system", "system", "CREATE DATABASE db3")
    server.execute("db3", "system", "CREATE VIEW v AS SELECT 1 AS x")
    with pytest.raises(Exception, match="Database db3 not found"):
        server.execute("db1", "alice", "SELECT x FROM db3.v")


def test_drop_role(server, alice):
    server.drop_role("alice")
    assert not server.authenticate("alice", "secret", "db1")
    assert server.get_databases_for_role("alice") == []
    # databases are kept by default
    assert server.get_databases() == ["db1"]


def test_drop_role_statement(server, alice):
    server.execute("system", "system", "DROP ROLE alice")
    assert not server.authenticate("alice", "secret", "db1")
    assert server.get_databases() == ["db1"]


def test_drop_role_with_databases(server, alice):
    server.create_role("bob", "pwd")
    server.create_database("owned", role="alice")
    server.grant("bob", "owned")
    server.grant("bob", "db1")

    server.execute("system", "system", "DROP ROLE alice WITH DATABASES")
    # only the databases alice administers are dropped, along with their grants
    assert server.get_databases() == ["db1"]
    assert server.get_databases_for_role("alice") == []
    assert server.get_databases_for_role("bob") == ["db1"]


def test_create_database_with_role(server):
    server.create_role("alice", "secret")
    db = server.create_database("db1", role="alice")
    assert db.name == "db1"
    assert server.authenticate("alice", "secret", "db1")
    assert server.get_database_for_role("alice", "db1").ddl_allowed


@pytest.fixture
def bob(server):
    server.create_role("bob", "pwd")
    return "bob"


def test_admin_can_grant_and_revoke(server, alice, bob):
    server.execute("system", "system", "GRANT ADMIN ON db1 TO alice")
    server.execute("db1", "alice", "GRANT ON db1 TO bob AS shared")
    assert server.authenticate("bob", "pwd", "shared")
    assert not server.get_database_for_role("bob", "db1").ddl_allowed

    server.execute("db1", "alice", "REVOKE ON db1 FROM bob")
    assert server.get_databases_for_role("bob") == []


def test_admin_can_grant_admin(server, alice, bob):
    server.execute("system", "system", "GRANT ADMIN ON db1 TO alice")
    server.execute("db1", "alice", "GRANT ADMIN ON db1 TO bob")
    assert server.get_database_for_role("bob", "db1").ddl_allowed
    # the new admin can manage grants too, including other admins
    server.execute("db1", "bob", "GRANT ON db1 TO alice")
    assert not server.get_database_for_role("alice", "db1").ddl_allowed


def test_admin_can_grant_using_alias(server, alice, bob):
    server.execute("system", "system", "GRANT ADMIN ON db1 TO alice AS mydb")
    server.execute("mydb", "alice", "GRANT ON mydb TO bob")
    assert server.get_databases_for_role("bob") == ["db1"]


def test_admin_can_grant_from_another_database(server, alice, bob):
    server.execute("system", "system", "CREATE DATABASE db2")
    server.execute("system", "system", "GRANT ADMIN ON db2 TO alice")
    # alice is connected to db1, where she is not admin
    server.execute("db1", "alice", "GRANT ON db2 TO bob")
    assert server.get_databases_for_role("bob") == ["db2"]


def test_non_admin_cannot_grant_or_revoke(server, alice, bob):
    server.grant("bob", "db1")
    with pytest.raises(DatabaseError, match="not admin"):
        server.execute("db1", "alice", "GRANT ADMIN ON db1 TO alice")
    with pytest.raises(DatabaseError, match="not admin"):
        server.execute("db1", "alice", "REVOKE ON db1 FROM bob")
    assert not server.get_database_for_role("alice", "db1").ddl_allowed
    assert server.get_databases_for_role("bob") == ["db1"]


def test_admin_cannot_grant_on_other_databases(server, alice, bob):
    server.execute("system", "system", "GRANT ADMIN ON db1 TO alice")
    server.execute("system", "system", "CREATE DATABASE db2")
    server.execute("system", "system", "GRANT ON db2 TO alice")
    for sql in ["GRANT ON db2 TO bob", "GRANT ADMIN ON db2 TO alice", "GRANT ON system TO bob", "GRANT ON nope TO bob"]:
        with pytest.raises(DatabaseError, match="not admin"):
            server.execute("db1", "alice", sql)
    assert server.get_databases_for_role("bob") == []


def test_admin_cannot_grant_to_unknown_role(server, alice):
    server.execute("system", "system", "GRANT ADMIN ON db1 TO alice")
    for role in ["carol", "system"]:
        with pytest.raises(DatabaseError, match=f"Role {role} not found"):
            server.execute("db1", "alice", f"GRANT ON db1 TO {role}")
