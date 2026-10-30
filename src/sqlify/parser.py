from lark import Lark, UnexpectedInput, UnexpectedToken
from importlib.resources import files
from sqletl.parser import ToAST as BaseToAST, unquote
from sqletl.errors import ParserError
from . import ast


# the sqlify grammar extends the sqletl one
_grammar = (files("sqletl") / "grammar.lark").read_text() + "\n" + \
           (files("sqlify") / "grammar.lark").read_text()
_parser = Lark(_grammar, parser="lalr", propagate_positions=True, maybe_placeholders=True)


def parse(sql):
    try:
        tree = _parser.parse(sql)
    except UnexpectedToken as e:
        if e.token.type == "$END":
            raise ParserError("Invalid SQL: unexpected end of statement") from e
        raise ParserError(f"Invalid SQL at line {e.line}, column {e.column}:\n{e.get_context(sql)}") from e
    except UnexpectedInput as e:
        raise ParserError(f"Invalid SQL at line {e.line}, column {e.column}:\n{e.get_context(sql)}") from e
    return ToAST(sql).transform(tree)


class ToAST(BaseToAST):
    def value(self, c):
        if c[0].type == "QUOTED_NAME":
            return unquote(c[0], '"')
        if c[0].type == "STRING":
            return unquote(c[0], "'")
        return str(c[0])

    def explain(self, c):
        return ast.Explain(c[0])

    # --- CREATE

    def create_alias(self, c):
        return ast.CreateAlias(*c)

    def create_view(self, c):
        materialized, name, select = c
        return ast.CreateView(name, select, materialized is not None)

    def create_scheme(self, c):
        return ast.CreateScheme(*c)

    def create_credentials(self, c):
        name, url, type_, value = c
        return ast.CreateCredentials(url, type_, value, name)

    def credentials_type(self, c):
        return c[0].lower()

    def create_pagination(self, c):
        url, param, location, name = c
        return ast.CreatePagination(url, param, location.lower(), name.strip())

    def create_header(self, c):
        _, url, header = c
        name, value = header.split(":", 1)
        return ast.CreateHeader(url, name.strip(), value.strip())

    def create_database(self, c):
        return ast.CreateDatabase(c[0])

    def create_schema(self, c):
        tables, columns, rows = [group[1:-1].strip() if group else None for group in c]
        return ast.CreateSchema(tables=tables, rows=rows, columns=columns)

    def create_role(self, c):
        return ast.CreateRole(*c)

    # --- DROP

    def drop_alias(self, c):
        return ast.DropAlias(c[0])

    def drop_view(self, c):
        return ast.DropView(c[0])

    def drop_scheme(self, c):
        return ast.DropScheme(c[0])

    def drop_credentials(self, c):
        return ast.DropCredentials(c[0])

    def drop_pagination(self, c):
        return ast.DropPagination(c[0])

    def drop_header(self, c):
        return ast.DropHeader(c[1])

    def drop_database(self, c):
        return ast.DropDatabase(c[0])

    def drop_schema(self, c):
        return ast.DropSchema()

    def drop_role(self, c):
        role, with_databases = c
        return ast.DropRole(role, with_databases is not None)

    # --- other statements

    def refresh_view(self, c):
        return ast.RefreshMaterializedView(c[1])

    def refresh_schema(self, c):
        return ast.RefreshSchema()

    def alter_role(self, c):
        role, password = c
        return ast.AlterRole(role, None if getattr(password, "type", None) == "NULL" else password)

    def grant(self, c):
        admin, database, role, alias = c
        return ast.Grant(role, database, admin is not None, alias)

    def revoke(self, c):
        database, role = c
        return ast.Revoke(role, database)

    def show(self, c):
        type_, *name = c
        return ast.Show(type_.lower(), " ".join(name) if name else None)
