from sqletl.ctx import Context as BaseContext, ContextError
from sqletl.protocols import (File, Http as BaseHttp, Fsspec as BaseFsspec, S3 as BaseS3, Postgresql as BasePostgresql,
                              Mysql as BaseMysql, GoogleSheets as BaseGoogleSheets, prepare_url)
from sqletl.reader import read_file, json_as_datatable
import itertools
import jsonpath_ng
import urllib.parse
import requests
import os


class Http(BaseHttp):
    def __init__(self, db):
        self.db = db

    def handle(self, ctx, method, url, params, content_type):
        pagination = self.db.get_pagination(url)
        if not pagination:
            return super().handle(ctx, method, url, params, content_type)
        
        url, fragment, params = prepare_url(url, params)
        jq = None
        if pagination.location in ("body", "json"):
            jq = jsonpath_ng.parse(pagination.name)

        merged_dt = None
        credentials = None
        while True:
            r, credentials = self.request(ctx, method, url, params, credentials=credentials, with_credentials=True)

            if pagination.location == "header":
                next_page = r.headers.get(pagination.name)
                if next_page:
                    params = dict(params, **{pagination.param: next_page})
                fd, response_content_type = self.process_response(r)
                dt = read_file(fd, url, fragment, content_type or response_content_type)
            else:
                data = r.json()
                next_page = jq.find(data)
                if next_page and next_page[0].value:
                    params = dict(params, **{pagination.param: next_page[0].value})
                else:
                    next_page = None
                dt = json_as_datatable(data, fragment)
            
            if not merged_dt:
                merged_dt = dt
            else:
                merged_dt.rows = itertools.chain(merged_dt.rows, dt.rows)

            if not next_page:
                return merged_dt
    
    def request(self, ctx, method, url, params, credentials=None, with_credentials=False, **kwargs):
        url, credentials = rewrite_url_with_credentials(self.db, url, credentials)
        kwargs.setdefault("headers", {}).update(self.db.get_headers(url))
        url = urllib.parse.urlparse(url)
        if url.username and url.password:
            kwargs["auth"] = (url.username, url.password)
        elif url.username:
            kwargs.setdefault("headers", {})["Authorization"] = f"Bearer {url.username}"
        elif credentials and credentials.type == "header":
            kwargs["headers"] = dict([credentials.value.split("=", 1)])
        elif credentials and credentials.type == "param":
            params.append(credentials.value.split("=", 1))
        url = rewrite_url_auth(url)
        r = super().request(ctx, method, url, params, **kwargs)
        return (r, credentials) if with_credentials else r
    

def apply_credentials_to_protocol(_class, override_method):
    def __init__(self, db, *args, **kwargs):
        _class.__init__(self, *args, **kwargs)
        self.db = db
    def method(self, url):
        return getattr(_class, override_method)(self, rewrite_url_with_credentials(self.db, url)[0])
    return type(_class.__name__, (_class,), {"__init__": __init__, override_method: method})
    

Fsspec = apply_credentials_to_protocol(BaseFsspec, "parse_url")
S3 = apply_credentials_to_protocol(BaseS3, "parse_url")
Postgresql = apply_credentials_to_protocol(BasePostgresql, "connect")
Mysql = apply_credentials_to_protocol(BaseMysql, "connect")
GoogleSheets = apply_credentials_to_protocol(BaseGoogleSheets, "parse_url")


class Context(BaseContext):
    def __init__(self, db, params=None):
        super().__init__(protocols={
            'http': Http(db),
            'https': Http(db),
            'file': File(db.files_dir),
            'ftp': Fsspec(db, "ftp"),
            's3': S3(db),
            'postgresql': Postgresql(db),
            'mysql': Mysql(db),
            'gsheets': GoogleSheets(db),
        })
        self.db = db
        self.params = params
        
    def load(self, uri, params, database=None):
        method = ""
        if uri.startswith("POST "):
            method = "POST "
            uri = uri[5:]

        if database and database.lower() == "information_schema":
            db = self.db.get_information_schema_db()
            return db.create_context().load(uri, params)
        elif database and self.db.name != database:
            db = self.db.server.get_database_for_role(self.db.role, database)
            if not db:
                raise ContextError(f"Database {database} not found")
            return db.create_context().load(uri, params)

        if self.params:
            uri = urllib.parse.urlparse(uri)
            if uri.query and (uri.query == "+" or uri.query.endswith("&+")):
                _params = dict(params)
                for k, v in self.params:
                    if k not in _params:
                        params.append((k, v))
                if uri.query == "+":
                    uri = uri._replace(query=None)
                else:
                    uri = uri._replace(query=uri.query[:-2])
            uri = uri.geturl()

        if "://" not in uri:
            if uri in self.db.aliases:
                return self.load(self.db.aliases[uri], params)
            return self.get_table(uri, params)
        
        scheme = uri.split("://")[0].lower()
        if scheme in self.db.schemes:
            uri = self.db.schemes[scheme].replace("$PATH", uri.split("://")[1])
        return super().load(f"{method}{uri}", params)

    def get_table(self, name, params=None):
        try:
            return super().get_table(name)
        except ContextError:
            return self.db.fetch(name, params, self)
        

def rewrite_url_with_credentials(db, url, credentials=None):
    if not credentials:
        credentials = db.get_credentials(url)
    if credentials:
        if credentials.type == "remote":
            r = requests.post(credentials.value, data={"db": db.name, "role": db.role})
            if r.status_code != 200:
                return url, None
            from .db import Credential
            credentials = Credential.from_dict(dict(credentials.to_dict(), **r.json()))
        if credentials.type == "auth":
            username, password = credentials.value.split(":")
            url = rewrite_url_auth(url, username, password)
        elif credentials.type == "token":
            url = rewrite_url_auth(url, credentials.value)
    return url, credentials


def rewrite_url_auth(url, username=None, password=None):
    if not isinstance(url, urllib.parse.ParseResult):
        url = urllib.parse.urlparse(url)
    netloc = url.netloc.split("@", 1)[-1]
    if username and password:
        netloc = f"{username}:{password}@{netloc}"
    elif username:
        netloc = f"{username}@{netloc}"
    return url._replace(netloc=netloc).geturl()