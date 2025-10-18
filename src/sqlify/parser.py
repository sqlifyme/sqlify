from sqletl.parser import Parser as BaseParser
from postgres_proto.sql.tokenizer import split_sql, unquote, tokenize_list
from . import ast
import re


def parse(sql):
    return Parser().parse(sql)


class Parser(BaseParser):
    def parse_explain(self, sql):
        return ast.Explain(self.parse(sql[8:]))

    def parse_create(self, sql):
        create_types = {
            "alias": r"^CREATE\s+ALIAS",
            "view": r"^CREATE(\s+MATERIALIZED)?\s+VIEW",
            "scheme": r"^CREATE\s+SCHEME",
            "credentials": r"^CREATE\s+CREDENTIALS",
            "pagination": r"^CREATE\s+PAGINATION",
            "header": r"^CREATE\s+HEADER",
            "database": r"^CREATE\s+DATABASE",
            "schema": r"^CREATE\s+SCHEMA",
            "role": r"^CREATE\s+ROLE",
        }
        for create_type, pattern in create_types.items():
            if re.match(pattern, sql, re.I):
                return getattr(self, f"parse_create_{create_type}")(sql)
        raise SyntaxError(f"Unknown CREATE statement: {sql}")
    
    def parse_create_alias(self, sql):
        parts = split_sql(sql, ("ALIAS", "AS"))
        return ast.CreateAlias(unquote(parts["ALIAS"]), unquote(parts["AS"]))
    
    def parse_create_view(self, sql):
        parts = split_sql(sql, ("MATERIALIZED", "VIEW", "AS"))
        return ast.CreateView(unquote(parts["VIEW"]), self.parse(parts["AS"]), "MATERIALIZED" in parts)
    
    def parse_create_scheme(self, sql):
        parts = split_sql(sql, ("SCHEME", "AS"))
        return ast.CreateScheme(unquote(parts["SCHEME"]), unquote(parts["AS"]))
    
    def parse_create_credentials(self, sql):
        types = ("TOKEN", "AUTH", "HEADER", "PARAM", "REMOTE")
        parts = split_sql(sql, ("CREDENTIALS", "ON", *types))
        auth_type = None
        auth_value = None
        for t in types:
            if t in parts:
                auth_type = t.lower()
                auth_value = unquote(parts[t].strip())
                break
        return ast.CreateCredentials(unquote(parts["ON"].strip()), auth_type, auth_value, unquote(parts["CREDENTIALS"]) if "CREDENTIALS" in parts else None)
    
    def parse_create_pagination(self, sql):
        parts = split_sql(sql, ("ON", "AS"))
        param, value = parts["AS"].split("=", 1)
        location, value = value.split('(')
        value = value.strip().rstrip(')')
        return ast.CreatePagination(unquote(parts["ON"].strip()), param.strip(), location.strip().lower(), value)
    
    def parse_create_header(self, sql):
        parts = split_sql(sql, ("ON", "AS"))
        param, value = unquote(parts["AS"]).split(":", 1)
        return ast.CreateHeader(unquote(parts["ON"].strip()), param.strip(), value.strip())
    
    def parse_create_database(self, sql):
        parts = split_sql(sql, ("DATABASE",))
        return ast.CreateDatabase(unquote(parts["DATABASE"]))
    
    def parse_create_schema(self, sql):
        keys = ("TABLES AS", "COLUMNS AS", "ROWS AS")
        parts = split_sql(sql, keys)
        config = {}
        if "TABLES AS" not in parts:
            raise SyntaxError("CREATE SCHEMA must include TABLES AS")
        if "ROWS AS" not in parts:
            raise SyntaxError("CREATE SCHEMA must include ROWS AS")
        for key in keys:
            config[key[:-3].lower()] = parts[key].strip()[1:-1] if key in parts else None
        return ast.CreateSchema(**config)
    
    def parse_create_role(self, sql):
        parts = split_sql(sql, ("ROLE", "PASSWORD"))
        return ast.CreateRole(unquote(parts["ROLE"]), unquote(parts["PASSWORD"]) if "PASSWORD" in parts else None)
    
    def parse_drop(self, sql):
        drop_types = {
            "alias": r"^DROP\s+ALIAS",
            "view": r"^DROP\s+VIEW",
            "scheme": r"^DROP\s+SCHEME",
            "credentials": r"^DROP\s+CREDENTIALS",
            "pagination": r"^DROP\s+PAGINATION",
            "header": r"^DROP\s+HEADER",
            "database": r"^DROP\s+DATABASE",
            "schema": r"^DROP\s+SCHEMA",
            "role": r"^DROP\s+ROLE",
        }
        for drop_type, pattern in drop_types.items():
            if re.match(pattern, sql, re.I):
                return getattr(self, f"parse_drop_{drop_type}")(sql)
        raise SyntaxError(f"Unknown DROP statement: {sql}")
    
    def parse_drop_alias(self, sql):
        parts = split_sql(sql, ("ALIAS",))
        return ast.DropAlias(unquote(parts["ALIAS"]))
    
    def parse_drop_view(self, sql):
        parts = split_sql(sql, ("VIEW",))
        return ast.DropView(unquote(parts["VIEW"]))
    
    def parse_drop_scheme(self, sql):
        parts = split_sql(sql, ("SCHEME",))
        return ast.DropScheme(unquote(parts["SCHEME"]))
    
    def parse_drop_credentials(self, sql):
        parts = split_sql(sql, ("CREDENTIALS",))
        return ast.DropCredentials(unquote(parts["CREDENTIALS"]))
    
    def parse_drop_pagination(self, sql):
        parts = split_sql(sql, ("PAGINATION",))
        return ast.DropPagination(unquote(parts["PAGINATION"]))
    
    def parse_drop_header(self, sql):
        parts = split_sql(sql, ("HEADER",))
        return ast.DropHeader(unquote(parts["HEADER"]))
    
    def parse_drop_database(self, sql):
        parts = split_sql(sql, ("DATABASE",))
        return ast.DropDatabase(unquote(parts["DATABASE"]))
    
    def parse_drop_schema(self, sql):
        return ast.DropSchema()
    
    def parse_drop_role(self, sql):
        parts = split_sql(sql, ("ROLE", "WITH DATABASES"))
        return ast.DropRole(unquote(parts["ROLE"]), "WITH DATABASES" in parts)
    
    def parse_refresh(self, sql):
        refresh_types = {
            "view": r"^REFRESH\s+MATERIALIZED\s+VIEW",
            "schema": r"^REFRESH\s+SCHEMA",
        }
        for refresh_type, pattern in refresh_types.items():
            if re.match(pattern, sql, re.I):
                return getattr(self, f"parse_refresh_{refresh_type}")(sql)
        raise SyntaxError(f"Unknown REFRESH statement: {sql}")
    
    def parse_refresh_view(self, sql):
        parts = split_sql(sql, ("VIEW",))
        return ast.RefreshMaterializedView(unquote(parts["VIEW"]))
    
    def parse_refresh_schema(self, sql):
        return ast.RefreshSchema()
    
    def parse_show(self, sql):
        parts = sql[5:].split(' ', 1)
        if len(parts) == 2:
            return ast.Show(parts[0].lower(), unquote(parts[1]))
        return ast.Show(parts[0].lower())
    
    def parse_alter(self, sql):
        alter_types = {
            "role": r"^ALTER\s+ROLE",
        }
        for alter_type, pattern in alter_types.items():
            if re.match(pattern, sql, re.I):
                return getattr(self, f"parse_alter_{alter_type}")(sql)
        raise SyntaxError(f"Unknown ALTER statement: {sql}")
    
    def parse_alter_role(self, sql):
        parts = split_sql(sql, ("ROLE", "PASSWORD"))
        return ast.AlterRole(unquote(parts["ROLE"]), unquote(parts["PASSWORD"]) if parts["PASSWORD"] != "NULL" else None)
    
    def parse_grant(self, sql):
        parts = split_sql(sql, ("ADMIN", "ON", "TO", "AS"))
        return ast.Grant(unquote(parts["TO"]), unquote(parts["ON"]), "ADMIN" in parts, unquote(parts["AS"]) if "AS" in parts else None)
    
    def parse_revoke(self, sql):
        parts = split_sql(sql, ("ON", "FROM"))
        return ast.Revoke(unquote(parts["FROM"]), unquote(parts["ON"]))