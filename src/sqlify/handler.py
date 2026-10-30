from postgres_proto.socket_handler import PostgresRequestHandler
from postgres_proto.flow import catch_all_as_postgres_error_context, PostgresError
from postgres_proto.sql.parser import iter_tables
from sqletl.errors import SqletlError
from .db import DatabaseError
import re
import json
import logging


logger = logging.getLogger("sqlify")


class RequestHandler(PostgresRequestHandler):
    def is_authentication_needed(self, username, database):
        return True

    def authenticate(self, username, password, database):
        if self.server.manager.authenticate(username, password, database):
            self.database = database
            return username

    def execute_query(self, query):
        logger.debug(query)

        stmt_type, stmt_info = self.parse_query(query)
        if self.is_postgres_builtins_query(stmt_type, stmt_info):
            return self.handle_postgres_builtins_query(stmt_type, stmt_info)
        
        with catch_all_as_postgres_error_context(logger):
            try:
                if re.match("use \w+", query, re.I):
                    self.database = query.split()[1]
                    return "USE", None, None
                if re.match("set role", query, re.I):
                    if self.user != "system":
                        raise Exception("Only system user can act as another user")
                    self.user = query[8:].strip()
                    return "SELECT", None, None
                if query.split(' ')[0].upper() in self.ignore_missing_statement_types:
                    return query.split(' ')[0].upper(), None, None
                dt = self.server.manager.execute(self.database, self.user, query)
                return "SELECT", format_rows(dt), dt.colnames
            except Exception as e:
                if stmt_type == "SELECT" and any(
                    t.schema == "information_schema" or "pg_" in f"{t.schema}.{t.name}".lower()
                    for t in iter_tables(stmt_info.tables)
                ):
                    return self.handle_postgres_builtins_query(stmt_type, stmt_info)
                if isinstance(e, SyntaxError):
                    raise PostgresError(f"Syntax error: {str(e)}")
                if isinstance(e, (SqletlError, DatabaseError)):
                    raise PostgresError(str(e))
                raise


def format_rows(dt):
    for row in dt:
        yield tuple(json.dumps(c) if isinstance(c, (list, dict)) else c for c in row)
