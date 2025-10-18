# Views

SQL views are possible in SQLify

## Managing views

```sql
CREATE VIEW myview AS SELECT * FROM "http://example.com";
SELECT * FROM myview;
```

To remove a view;

```sql
DROP VIEW myview
```

## Materialized views

Materialized views are also possible. SQLify will put the data in cache for a few days. Refreshing is done manually:

```sql
CREATE MATERIALIZED VIEW myview AS SELECT * FROM "http://example.com";
SELECT * FROM myview;
REFRESH MATERIALIZED VIEW myview;
```
