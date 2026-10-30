# Getting started

SQLify is a new kind of database which does not store any data.

At the core of SQLify is the capability to query various remote data sources using SQL. To do so,
we have added new capabilities to SQL. We call this superset [SQLETL](sqletl.md).

There are no tables in an SQLify database. All the data is accessed in real-time when a query is
performed.

SQLify speaks the PostgreSQL protocol: you can connect to it with psql, BI tools or any
PostgreSQL driver.

## Installation

No need for installation if using [uv](https://docs.astral.sh/uv/):

    $ uvx sqlify

But if you are planning to use it frequently:

    $ uv tool install sqlify

## Starting the server

    $ SQLIFY_SYSTEM_PWD=password sqlify

The server listens on `127.0.0.1:55432` by default. Options: `--listen-addr`, `--port`,
`--ssl-cert`, `--ssl-key`, `--max-clients`.

Databases, roles and their configuration are stored in a `sqlify.db` file in the current
directory.

## First queries

The server exposes a *system* user and a *system* database for administrative purposes.

    $ psql -h localhost -U system -p 55432 system

Query a URL directly:

```sql
SELECT * FROM "http://example.com/path" WHERE "?param" = 'value';
```

Create a database and a role (see [databases and roles](roles.md)):

```sql
CREATE DATABASE mydb;
CREATE ROLE alice PASSWORD 'secret';
GRANT ON mydb TO alice;
```

Then, connected to `mydb`, store [credentials](credentials.md) and create [views](views.md):

```sql
CREATE CREDENTIALS ON "https://api.example.com" TOKEN 'my-token';
CREATE VIEW users AS SELECT * FROM "https://api.example.com/users";
SELECT * FROM users;
```
