#!/usr/local/bin/python3
import sys
from functools import partial

import bokeh_app
from bokeh.server.server import Server as BokehServer
import data_storage
import depolarizer
import GEM_handler
from config import config


def main():
    # freq storage
    init_data = data_storage.get_init_data()
    freq_storage_ = data_storage.FreqMap(config.asym_buffer_len, init_data)

    # depolarizer
    if sys.version[0] == '2':
        ConnectionRefusedError = Exception
    try:
        depolarizer_ = depolarizer.Depolarizer('192.168.176.61', 9090, freq_storage_)
        depolarizer_.start_fmap()
        depolarizer_.start_update()
    except ConnectionRefusedError as e:
        print(e)
        print("Unable to connect to depolarizer")
        depolarizer_ = depolarizer.FakeDepolarizer()

    # Storages

    hist_storage_ = data_storage.HistStorage(config.GEM_X, config.GEM_Y, config.hist_buffer_len)
    data_storage_ = data_storage.ChunkStorage(config.asym_buffer_len, init_data, depolarizer_, freq_storage_)

    # GEM_handler
    GEM_handler_ = GEM_handler.GEM_handler(hist_storage_, data_storage_, sleeping_time=config.GEM_slipping_time)
    GEM_handler_.start()

    # Bokeh server
    app = partial(bokeh_app.app,
                  hist_storage_=hist_storage_, data_storage_=data_storage_, freq_storage_=freq_storage_,
                  depolarizer=depolarizer_, names=data_storage.names)
    bokeh_server_ = BokehServer(app,
                                allow_websocket_origin=config.ip_list,
                                num_procs=1,
                                port=config.web_port,
                                prefix='lsrp')

    bokeh_server_.io_loop.start()


if __name__ == "__main__":
    main()
