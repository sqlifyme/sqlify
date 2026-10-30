# Database

## Querying across databases

You can join tables from different databases by prefixing the table name with the database name.
The current role must have access to both databases.

```sql
SELECT * FROM "my table in current db" t1 JOIN "other database"."table in other db" t2 ON ...
```

You can query any data source as if it was from another database. This is useful to re-use
credentials from another db.

```sql
SELECT * FROM "other database"."https://api.example.com/users"
```

## Setting up a database schema

SQLify provides a way to define a dynamic schema for your database using the `CREATE SCHEMA` statement.

```sql
CREATE SCHEMA WITH
    TABLES AS (SELECT ...)
    COLUMNS AS (SELECT ...)
    ROWS AS (SELECT ...)
```

`TABLES AS` defines a select statement that returns a list of tables. It is mandatory to return at least a "name" column.

`COLUMNS AS` is optional. It defines a select statement that returns a list of columns. It is mandatory to return at least a "name" column.

`ROWS AS` defines a select statement that returns the rows for the table.

Select statements from `COLUMNS AS` and `ROWS AS` can access data from the current table using `$TABLE[column_name]`.

Example with Notion:

```sql
CREATE SCHEMA WITH
    TABLES AS (
        SELECT id, title->0->plain_text AS name
        FROM "POST https://api.notion.com/v1/search?JSON#results"
        WHERE "?filter.value" = 'database' AND "?filter.property" = 'object'
    )
    COLUMNS AS (
        WITH props AS (
            SELECT unnest(properties)
            FROM "https://api.notion.com/v1/databases/$TABLE[id]"
        )
        SELECT value->id AS id, key AS name FROM props
    )
    ROWS AS (
        SELECT id, expand(properties)
        FROM "POST https://api.notion.com/v1/databases/$TABLE[id]/query#results"
    )
```

Query parameters can be forwarded to the underlying query by using the "+" parameter:

```sql
SELECT id, expand(properties)
FROM "POST https://api.notion.com/v1/databases/$TABLE[id]/query?+#results"
```

The list of tables and columns is fetched when the schema is created. Fetch it again with:

```sql
REFRESH SCHEMA
```

To inspect the schema:

```sql
SHOW SCHEMA;
SHOW TABLES;
SHOW TABLE mytable;  -- columns of a table
```

Tables and views are also listed in `information_schema`, so PostgreSQL clients can browse them.

To remove the schema:

```sql
DROP SCHEMA
```
