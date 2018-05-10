import threading
from time import sleep
from itertools import chain
from math import floor

import numpy as np

import cpp.GEM as GEM
from data_storage import hist_storage_, data_storage_
from config import config
from hit_dump_parser import read_hitdump


class GEM_handler(threading.Thread):

    def __init__(self, sleeping_time=1):
        """
        Получает данные от GEM, усредняет их и складывает их в data_storage

        :param sleeping_time: интервал между опросами детектора
        """
        threading.Thread.__init__(self, name='GEM_handler')
        self.GEM = GEM
        self.sleeping_time = sleeping_time
        self.buf = []
        self.start_time = None
        self.delta_time = config.delta_time
        self.X = config.GEM_X
        self.Y = config.GEM_Y

    def get_data(self):
        if config.read_hitdump:
            data = read_hitdump()
        elif config.GEM_idle:
            data = self.GEM.debug_data()
        else:
            data = self.GEM.GEM_reco()

        hist_storage_.add_as_GEM_struct_array(data)

        if len(data) == 0:
            return

        end_time = data[-1].timestamp - self.delta_time
        first_data_time = data[0].timestamp
        if self.start_time is None:
            self.start_time = first_data_time

        x_online_l, y_online_l, x_online_r, y_online_r,  = 0, 0, 0, 0
        x_cog_l, y_cog_l, x_cog_r, y_cog_r = 0, 0, 0, 0
        counter_l, counter_r, charge = 0, 0, 0
        new_buf = []

        while self.start_time + self.delta_time < first_data_time:
            self.start_time += self.delta_time
        for hit_struct in chain(self.buf, data):
            if self.start_time < end_time:
                if hit_struct.timestamp < self.start_time + self.delta_time:
                    r_x, r_y = floor(hit_struct.x_online), floor(hit_struct.y_online)

                    if not ((0 <= r_x < self.X) and (0 <= r_y < self.Y)):
                        continue

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
        if not config.GEM_idle:
            try:
                self.GEM.init()
            except:
                print('Can\'t init GEM!')
        if config.read_hitdump:
            self.get_data()
        else:
            while True:
                sleep(self.sleeping_time)
                self.get_data()
