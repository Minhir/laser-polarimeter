import threading
from time import sleep
from itertools import chain

import cpp.GEM as GEM
from data_storage import hist_storage_, data_storage_


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

    def get_data(self):
        if self.debug:
            data = self.GEM.debug_data()
        else:
            data = self.GEM.GEM_reco()

        hist_storage_.add_as_array([i.x_cog for i in data], [i.y_cog for i in data])  # TODO добавить обе реконструкции

        delta_time = 0.1
        first = True
        x_online_l, y_online_l, x_online_r, y_online_r = 0, 0, 0, 0
        x_cog_l, y_cog_l, x_cog_r, y_cog_r = 0, 0, 0, 0
        counter_l, counter_r = 0, 0
        end_point = 0

        for hit_struct in chain(self.buf, data):
            end_point += 1

            if first:
                start_time = hit_struct.timestamp
                first = False

            if hit_struct.timestamp <= start_time + delta_time:
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
                start_time += delta_time
                if counter_l == 0 or counter_r == 0:
                    continue

                data_storage_.add([(start_time - delta_time / 2,
                                   x_online_l / counter_l, y_online_l / counter_l,
                                   x_online_r / counter_r, y_online_r / counter_r,
                                   x_cog_l    / counter_l, y_cog_l    / counter_l,
                                   x_cog_r    / counter_r, y_cog_r    / counter_r,
                                   x_online_l / counter_l - x_online_r / counter_r,
                                   y_online_l / counter_l - y_online_r / counter_r,
                                   x_cog_l / counter_l - x_cog_r / counter_r,
                                   y_cog_l / counter_l - y_cog_r / counter_r)])

                x_online_l, y_online_l, x_online_r, y_online_r = 0, 0, 0, 0
                x_cog_l, y_cog_l, x_cog_r, y_cog_r = 0, 0, 0, 0
                counter_l, counter_r = 0, 0

        new_buf = []
        if end_point > len(self.buf):
            new_buf += data[end_point - len(self.buf):]
        else:
            new_buf = self.buf[end_point:]
            new_buf += data[:]
        self.buf = new_buf

    def run(self):
        try:
            if not self.debug:
                self.GEM.init()
        except :                            # TODO: уточнить
            print('Can\'t init GEM!')

        while True:
            sleep(self.sleeping_time)
            self.get_data()
