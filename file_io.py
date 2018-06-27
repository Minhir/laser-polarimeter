import os
import datetime
import time
import threading

import re
import numpy as np

from config import config


class FileIO (threading.Thread):

    def __init__(self):
        """
        Читает/записывает данные.
        Формат: папка dir_format= "%y.%m.%d"
        Файлы: hh_mm_ss.npz
        """
        threading.Thread.__init__(self, name='FileIO thread')
        self.file_pattern = re.compile("^[0-2][0-9]_[0-6][0-9]_[0-6][0-9]\.npz$")
        self.dir_patter = re.compile("^[0-3][0-9]\.[0-1][0-9]\.[0-9][0-9]$")
        self.dir_format = "%y.%m.%d"
        self.dir_ = "data"
        if not os.path.isdir(self.dir_):
            os.mkdir(self.dir_)

        self.depol_buffer = []
        self.asym_data_buffer = []
        self.freq_dtype = np.dtype([('time', np.float64), ('freq', np.float32)])
        self.writing_delta_time = config.writing_delta_time
        self.last_time = time.time()
        self.lock = threading.Lock()

    def read_from_file(self):
        data = {}
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)

        for day in [yesterday, today]:
            dir_name = day.strftime(self.dir_format)
            dir_path = self.dir_ + '/' + dir_name
            if not self.dir_patter.match(dir_name) or not os.path.isdir(dir_path):
                continue

            for file in sorted(os.listdir(dir_path)):
                file_path = dir_path + '/' + file
                if self.file_pattern.match(file) and os.path.isfile(file_path):
                    with np.load(file=file_path) as npz:
                        for key_ in npz.keys():
                            if key_ not in data:
                                data[key_] = []
                            for item in npz[key_]:
                                data[key_].append(item)
        return data

    def add_chunk_data(self, data):
        """Добавляет chunk"""
        with self.lock:
            self.asym_data_buffer.append(data)

    def add_freq_data(self, time_, freq):
        """Добавляет данные в карту частот"""
        with self.lock:
            self.depol_buffer.append(np.array((time_, freq), dtype=self.freq_dtype))

    def write_to_file(self):
        if not self.asym_data_buffer:
            return

        today = datetime.date.today().strftime(self.dir_format)
        if not os.path.isdir(self.dir_ + '/' + today):
            os.mkdir(self.dir_ + '/' + today)

        now = datetime.datetime.now().strftime("%H_%M_%S.npz")
        with self.lock:
            np.savez(self.dir_ + '/' + today + '/' + now, asym_data=self.asym_data_buffer, depol_data=self.depol_buffer)
            self.asym_data_buffer.clear()
            self.depol_buffer.clear()

    def run(self):
        while True:
            time.sleep(self.writing_delta_time)
            self.write_to_file()


file_io = FileIO()
file_io.start()
