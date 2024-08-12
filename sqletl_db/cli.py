from .server import Server
from .handler import RequestHandler
from postgres_proto.server import start_server, cli_arg_parser
import logging


def main():
    logging.basicConfig(level=logging.DEBUG)
    kwargs = vars(cli_arg_parser.parse_args())
    manager = Server("data/auth.db")
    start_server(RequestHandler, manager=manager, **kwargs)