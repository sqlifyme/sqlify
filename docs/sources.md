# Data sources

These statements configure how data sources are accessed in the current database. They are
stored with the database and apply to every query.

## Aliases

An alias gives a table name to a URI.

```sql
CREATE ALIAS users AS "https://api.example.com/users#data";
SELECT * FROM users;
```

```sql
SHOW ALIASES;
DROP ALIAS users;
```

## Schemes

A scheme defines a custom URI scheme. `$PATH` is replaced with everything after `://`.

```sql
CREATE SCHEME gh AS "https://api.github.com/$PATH";
SELECT * FROM "gh://repos/sqlifyme/sqlify/issues";
```

```sql
SHOW SCHEMES;
DROP SCHEME gh;
```

## Headers

Add an HTTP header to all requests whose URL starts with the given URL. Several headers can be
added to the same URL.

```sql
CREATE HEADER ON "https://api.notion.com" AS 'Notion-Version: 2022-06-28';
```

```sql
SHOW HEADERS;
DROP HEADER "https://api.notion.com";  -- removes all headers for this URL
```

To send a secret in a header, use [credentials](credentials.md#header) instead: their values are
never displayed.

## Pagination

Paginated HTTP APIs can be fetched in full. SQLify keeps requesting pages and merges the rows
until there is no next page.

    CREATE PAGINATION ON "<url>" AS <param>=<location>(<name>)

- `param`: the query parameter used to request the next page
- `location`: where to find the value of the next page in the response, either `header` or `body`
- `name`: the header name, or a JSONPath in the response body

```sql
-- next page value in the "next_cursor" field of the JSON body, sent as ?cursor=...
CREATE PAGINATION ON "https://api.example.com" AS cursor=body(next_cursor);

-- next page value in the X-Next-Page response header, sent as ?page=...
CREATE PAGINATION ON "https://other.example.com" AS page=header(X-Next-Page);
```

```sql
SHOW PAGINATIONS;
DROP PAGINATION "https://api.example.com";
```

## URL matching

Credentials, headers and pagination rules apply to every URL starting with the rule's URL. When
several rules match, the longest one wins. `*` can be used as a path segment:
`"https://example.com/*/items"`.
