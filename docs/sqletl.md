# SQLETL

SQLify queries are written in SQLETL, a superset of SQL provided by the
[sqletl](https://sqlifyme.github.io/sqletl/) library. Everything that works in sqletl works in
SQLify.

**The full SQLETL reference is available at [sqlifyme.github.io/sqletl](https://sqlifyme.github.io/sqletl/).**

## Overview

The main idea of SQLETL is that a table name can be a URI. The data is fetched, parsed and
transformed when the query runs:

```sql
SELECT u.name, COUNT(*) AS orders
FROM "https://api.example.com/users#data" u
JOIN "s3:///my-bucket/orders.parquet" o ON o.user_id = u.id
GROUP BY u.name
```

- **Sources**: HTTP(S) (GET and POST), files, S3, FTP, PostgreSQL, MySQL, Google Sheets
  ([protocols](https://sqlifyme.github.io/sqletl/protocols/))
- **Formats**: JSON, CSV, XLSX, Parquet, SQLite, detected automatically or forced with
  `scheme+format://` ([data formats](https://sqlifyme.github.io/sqletl/data-formats/))
- **Request parameters from SQL**: `WHERE "?param" = 'value'` is sent to the source as a request
  parameter, and URL templates such as `"https://example.com/users/{id}"` are filled from
  `WHERE "?id" = 1` ([HTTP](https://sqlifyme.github.io/sqletl/http/))
- **Nested data**: select rows with a JSONPath in the URI fragment (`#data.items`), access fields
  with `->` / `->>`, flatten with `EXPAND()` and `UNNEST()`
- **SQL processing**: joins, `GROUP BY`, window functions, `ORDER BY`, `LIMIT`, CTEs

Some SQL features are not supported yet, see the
[limitations](https://sqlifyme.github.io/sqletl/limitations/).

## What SQLify adds

SQLify runs SQLETL queries as a PostgreSQL compatible server and adds statements to manage
what is stored in a database:

- [Credentials](credentials.md) so that secrets are not written in queries
- [Aliases, schemes, headers and pagination](sources.md) for data sources
- [Views](views.md) and [schemas](database.md#setting-up-a-database-schema)
- [Databases and roles](roles.md)

Use `EXPLAIN` to see how a query will be executed without running it:

```sql
EXPLAIN SELECT * FROM "https://example.com/api/items" WHERE "?q" = 'a' OR "?q" = 'b'
```

!!! note
    In SQLify, `file://` URIs are relative to a folder dedicated to each database
    (`user_files/<database>` next to the server's `sqlify.db` file) and cannot reach files
    outside of it.
