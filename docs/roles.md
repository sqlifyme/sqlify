# Databases and roles

Databases and roles are managed from the *system* database, connected as the *system* user
(database admins can also manage access to their databases, see below). The
*system* user's password is set with the `SQLIFY_SYSTEM_PWD` environment variable when starting
the server. Without it, the *system* user cannot log in.

## Databases

```sql
CREATE DATABASE mydb;
DROP DATABASE mydb;
SHOW DATABASES;
```

When connected as another role, `SHOW DATABASES` lists the databases the role has access to.

## Roles

```sql
CREATE ROLE alice PASSWORD 'secret';
ALTER ROLE alice PASSWORD 'other';
```

A role without a password cannot log in. To disable a role, remove its password:

```sql
ALTER ROLE alice PASSWORD NULL;
```

Dropping a role removes its grants. The databases are kept unless `WITH DATABASES` is used, in
which case the databases the role administers are dropped too:

```sql
DROP ROLE alice;
DROP ROLE alice WITH DATABASES;
```

## Grants

A role can only connect to the databases it has been granted access to.

```sql
GRANT ON mydb TO alice;
REVOKE ON mydb FROM alice;
```

By default, access is read-only: the role can run queries but cannot change the database
(views, credentials, schema...). To allow it, grant admin access:

```sql
GRANT ADMIN ON mydb TO alice;
```

A database can be exposed to a role under another name. Here, alice connects to `analytics`,
which is the `mydb` database:

```sql
GRANT ON mydb TO alice AS analytics;
```

Granting again on the same database replaces the previous grant.

### Delegating access management

Admins of a database can also grant and revoke access to it, including admin access, without
going through the *system* user. They can do so while connected to any database they have
access to, and can refer to the database by its alias:

```sql
-- connected as alice, admin of mydb
GRANT ON mydb TO bob;
GRANT ADMIN ON mydb TO carol;
REVOKE ON mydb FROM bob;
```

The role must already exist: only the *system* user can create roles. Admins cannot grant or
revoke access to databases they do not administer.

## Acting as another role

Connected as the *system* user, you can run queries as another role:

```sql
SET ROLE alice
```
