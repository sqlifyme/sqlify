# Credentials

Credentials can be centrally managed instead of being provided for each query.

## Username/password

Create a set of HTTP auth credentials for an endpoint.

    CREATE CREDENTIALS ON "http://example.com/path" AUTH 'username:password'
    CREATE CREDENTIALS ON "postgresql://myserver.com" AUTH 'username:password'
    CREATE CREDENTIALS ON "s3:///bucket" AUTH 'aws_key:aws_secret'

## Bearer token

A "Bearer" token that will be provided through the Authentication header

    CREATE CREDENTIALS ON "http://example.com/path" TOKEN 'token'

## Header

A value that will be added as header

    CREATE CREDENTIALS ON "http://example.com/path" HEADER 'X-Header=value'

## Query parameter

A value that will be added as query parameter

    CREATE CREDENTIALS ON "http://example.com/path" PARAM 'name=value'

## Naming credentials rules

You can name rules:

    CREATE CREDENTIALS cred1 ON "http://example.com/path" TOKEN 'token'

Then use the named rule:

    SELECT * FROM "http://cred1@example.com/path/to/rest/endpoint"

## Removing a credentials rule

    DROP CREDENTIALS ON "http://example.com/path"
