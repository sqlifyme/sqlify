# SQLify

PostgreSQL compatible server on top of [sqletl](https://github.com/sqlify/sqletl)

## Installation

No need for installation if using [uv](https://docs.astral.sh/uv/):

    $ uvx sqlify

But if you are planning to use fequently:

    $ uv tool install sqlify

## Usage

The SQLify server exposes a *system* user and *system* database for administrative purposes.

Start the server:

    $ SQLIFY_SYSTEM_PWD=password sqlify

Connect using psql:

    $ psql -h localhost -U system -p 55432 system
    > SELECT * FROM "http://example.com/path" WHERE "?param" = 'value';