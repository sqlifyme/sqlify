# SQLify

PostgreSQL compatible server on top of [sqletl](https://github.com/sqlify/sqletl).

SQLify is a database that stores no data. Tables are remote data sources (HTTP APIs, files,
other databases...) queried in real time using SQL. Any PostgreSQL client (psql, BI tools,
drivers) can connect to it.

## Features

- **Query anything with SQL**: use URLs as table names, powered by the sqletl SQL superset
- **PostgreSQL wire protocol**: connect with psql or any PostgreSQL client
- **Databases and roles**: multiple databases, users with passwords and per-database grants
- **Credentials**: store auth (basic, bearer token, header, query param) per endpoint instead of in every query
- **Views**: regular and materialized (cached) views
- **Dynamic schemas**: expose a remote API as a set of tables with `CREATE SCHEMA`
- **Cross-database queries**: join tables from different databases

## Installation

No need for installation if using [uv](https://docs.astral.sh/uv/):

    $ uvx sqlify

But if you are planning to use it frequently:

    $ uv tool install sqlify

## Usage

The SQLify server exposes a *system* user and *system* database for administrative purposes.

Start the server (listens on `127.0.0.1:55432` by default):

    $ SQLIFY_SYSTEM_PWD=password sqlify

Options: `--listen-addr`, `--port`, `--ssl-cert`, `--ssl-key`, `--max-clients`.

Connect using psql:

    $ psql -h localhost -U system -p 55432 system
    > SELECT * FROM "http://example.com/path" WHERE "?param" = 'value';

Create a database and a user from the *system* database:

    > CREATE DATABASE mydb;
    > CREATE ROLE alice PASSWORD secret;
    > GRANT ON mydb TO alice;

Then, connected to `mydb`, store credentials and create views:

    > CREATE CREDENTIALS ON "https://api.example.com" TOKEN 'my-token';
    > CREATE VIEW users AS SELECT * FROM "https://api.example.com/users";
    > SELECT * FROM users;

## Documentation

See the [docs](docs/) folder: [credentials](docs/credentials.md), [databases and schemas](docs/database.md),
[views](docs/views.md).
