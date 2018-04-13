import threading
from time import sleep
from itertools import chain

import numpy as np

import cpp.GEM as GEM
from data_storage import hist_storage_, data_storage_
from config import config


class GEM_handler(threading.Thread):

    def __init__(self, debug=False, sleeping_time=1):
        """
        Получает данные от GEM и складывает их в data_storage

        :param debug: режим отладки, когда идут смоделированные данные
        :param sleeping_time: интервал между опросами детектора
        """
        threading.Thread.__init__(self, name='GEM_handler')
        self.GEM = GEM
        self.debug = debug
        self.sleeping_time = sleeping_time
        self.buf = []
        self.start_time = None
        self.delta_time = config.delta_time

    def get_data(self):
        data = self.GEM.debug_data() if self.debug else self.GEM.GEM_reco()

        hist_storage_.add_as_array([i.x_online for i in data], [i.y_online for i in data])

        if len(data) != 0:
            end_time = data[-1].timestamp - self.delta_time
            first_data_time = data[0].timestamp
            if self.start_time is None:
                self.start_time = first_data_time
        else:
            return

        x_online_l, y_online_l, x_online_r, y_online_r,  = 0, 0, 0, 0
        x_cog_l, y_cog_l, x_cog_r, y_cog_r = 0, 0, 0, 0
        counter_l, counter_r, charge = 0, 0, 0
        new_buf = []

        while self.start_time + self.delta_time < first_data_time:
            self.start_time += self.delta_time

        for hit_struct in chain(self.buf, data):
            if self.start_time < end_time:
                if hit_struct.timestamp < self.start_time + self.delta_time:
                    charge += hit_struct.charge
                    if hit_struct.polarity == 0:
                        counter_l += 1
                        x_online_l += hit_struct.x_online
                        y_online_l += hit_struct.y_online
                        x_cog_l += hit_struct.x_cog
                        y_cog_l += hit_struct.y_cog
                    else:
                        counter_r += 1
                        x_online_r += hit_struct.x_online
                        y_online_r += hit_struct.y_online
                        x_cog_r += hit_struct.x_cog
                        y_cog_r += hit_struct.y_cog
                else:
                    if counter_l != 0 or counter_r != 0:

                        if counter_l == 0:
                            counter_l = np.nan

                        if counter_r == 0:
                            counter_r = np.nan

                        data_storage_.add((self.start_time + self.delta_time / 2,
                                           x_online_l / counter_l, y_online_l / counter_l,
                                           x_online_r / counter_r, y_online_r / counter_r,
                                           x_cog_l    / counter_l, y_cog_l    / counter_l,
                                           x_cog_r    / counter_r, y_cog_r    / counter_r,
                                           x_online_l / counter_l - x_online_r / counter_r,
                                           y_online_l / counter_l - y_online_r / counter_r,
                                           x_cog_l / counter_l - x_cog_r / counter_r,
                                           y_cog_l / counter_l - y_cog_r / counter_r,
                                           counter_l, counter_r, charge / (counter_l + counter_r)))

                    self.start_time += self.delta_time
                    x_online_l, y_online_l, x_online_r, y_online_r = 0, 0, 0, 0
                    x_cog_l, y_cog_l, x_cog_r, y_cog_r = 0, 0, 0, 0
                    counter_l, counter_r, charge = 0, 0, 0
            else:
                new_buf.append(hit_struct)

        self.buf = new_buf[:]

    def run(self):
        try:
            if not self.debug:
                self.GEM.init()
        except :                            # TODO: уточнить
            print('Can\'t init GEM!')

        while True:
            sleep(self.sleeping_time)
            self.get_data()
