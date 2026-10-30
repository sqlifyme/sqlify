# Credentials

Credentials can be centrally managed instead of being provided for each query. They apply to
every URL starting with the given URL (see [URL matching](sources.md#url-matching)).

## Username/password

Create a set of HTTP auth credentials for an endpoint.

```sql
CREATE CREDENTIALS ON "http://example.com/path" AUTH 'username:password'
CREATE CREDENTIALS ON "postgresql://myserver.com" AUTH 'username:password'
CREATE CREDENTIALS ON "s3:///bucket" AUTH 'aws_key:aws_secret'
```

## Bearer token

A "Bearer" token that will be provided through the Authorization header

```sql
CREATE CREDENTIALS ON "http://example.com/path" TOKEN 'token'
```

## Header

A value that will be added as header

```sql
CREATE CREDENTIALS ON "http://example.com/path" HEADER 'X-Header=value'
```

## Query parameter

A value that will be added as query parameter

```sql
CREATE CREDENTIALS ON "http://example.com/path" PARAM 'name=value'
```

## Remote

Credentials can be fetched from another service when a query is executed. SQLify sends a POST
request to the given URL with the `db` and `role` form fields. The service must respond with a
JSON object providing the credentials `type` (`auth`, `token`, `header` or `param`) and `value`.

```sql
CREATE CREDENTIALS ON "http://example.com/path" REMOTE 'https://vault.example.com/credentials'
```

If the service does not respond with a 200 status code, no credentials are used.

## Naming credentials rules

You can name rules:

```sql
CREATE CREDENTIALS cred1 ON "http://example.com/path" TOKEN 'token'
```

Then use the named rule:

```sql
SELECT * FROM "http://cred1@example.com/path/to/rest/endpoint"
```

When a URL contains a username and password (`http://user:pass@example.com`), stored credentials
are not used.

## Listing credentials

Credential values are never displayed.

```sql
SHOW CREDENTIALS
```

## Removing a credentials rule

```sql
DROP CREDENTIALS ON "http://example.com/path"
DROP CREDENTIALS cred1
```
