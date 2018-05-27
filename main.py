#!/usr/local/bin/python3
from bokeh_app import app
from bokeh.server.server import Server as BokehServer
from GEM_handler import GEM_handler
from config import config


def main():
    GEM_handler_ = GEM_handler(sleeping_time=config.GEM_slipping_time)
    GEM_handler_.start()

    bokeh_server_ = BokehServer(app,
                                allow_websocket_origin=config.ip_list,
                                num_procs=1,
                                port=config.web_port,
                                prefix='lsrp')

    bokeh_server_.io_loop.start()


if __name__ == "__main__":
    main()
