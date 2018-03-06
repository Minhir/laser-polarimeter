import cpp.GEM as GEM
import threading
from time import sleep
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

    def get_data(self):
        if self.debug:
            data = self.GEM.debug_data()
        else:
            data = self.GEM.GEM_reco()

        hist_storage_.add_as_array([i.x_cog for i in data], [i.y_cog for i in data])  # TODO добавить обе реконструкции
        data_storage_.add([(i.timestamp, i.polarity, i.x_online, i.y_online, i.x_cog, i.y_cog) for i in data])
        # global b
        # data_storage_.add([(i / 100, 0, 0, sin(i / 100), 0, 0) for i in range(b, b + 1000)])
        # b += 1000

    def run(self):
        try:
            if not self.debug:
                self.GEM.init()
        except :                            # TODO: уточнить
            print('Can\'t init GEM!')

        while True:
            sleep(self.sleeping_time)
            self.get_data()
