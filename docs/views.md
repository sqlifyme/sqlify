# Views

SQL views are possible in SQLify

## Managing views

```sql
CREATE VIEW myview AS SELECT * FROM "http://example.com";
SELECT * FROM myview;
```

To list views and show the query of a view:

```sql
SHOW VIEWS;
SHOW VIEW myview;
```

To remove a view;

```sql
DROP VIEW myview
```

## Materialized views

Materialized views are also possible. SQLify caches the data when the view is created. Refreshing
is done manually:

```sql
CREATE MATERIALIZED VIEW myview AS SELECT * FROM "http://example.com";
SELECT * FROM myview;
REFRESH MATERIALIZED VIEW myview;
```
