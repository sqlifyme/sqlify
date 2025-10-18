# Database

## Querying across databases

You can join tables from different databases by prefixing the table name with the database name.

```sql
SELECT * FROM "my table in current db" t1 JOIN "other database"."table in other db" t2 ON ...
```

You can query any data source as if it was from another database. This is useful to re-use credentials from another db.

## Setting up a database schema

SQLify provides a way to define a dynamic schema for your database using the `CREATE SCHEMA` statement.

    CREATE SCHEMA WITH
        TABLES AS (SELECT ...)
        COLUMNS AS (SELECT ...)
        ROWS AS (SELECT ...)

Each SELECT statement

`TABLES AS` defines a select statement that returns a list of tables. It is mandatory to return at least a "name" column.

`COLUMNS AS` is optionnal. It defines a select statement that returns a list of columns. It is mandatory to return at least a "name" column.

`ROWS AS` defines a select statement that returns the rows for the table.

Select statements from `COLUMNS AS` and `ROWS AS` can access data from the current table using `$TABLE[column_name]`.

Example with Notion:

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

Query parameters can be forwared to the underlying query by using the "+" parameter:

            SELECT id, expand(properties)
            FROM "POST https://api.notion.com/v1/databases/$TABLE[id]/query?+#results"
