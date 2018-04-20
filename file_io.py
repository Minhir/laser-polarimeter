import os
import datetime

import re
import numpy as np

from config import config


class FileIO:

    def __init__(self):
        """
        Читает/записывает данные.
        Формат: папка dd.mm.yy = '%d.%m.%y'
        Файлы: hh_mm_ss.npz
        """
        self.file_pattern = re.compile("^[0-2][0-9]_[0-6][0-9]_[0-6][0-9]\.npz$")
        self.dir_patter = re.compile("^[0-3][0-9]\.[0-1][0-9]\.[0-9][0-9]$")
        self.dir_ = "data"
        if not os.path.isdir(self.dir_):
            os.mkdir(self.dir_)

        self.buffer = []
        self.writing_delta_time = config.writing_delta_time
        self.last_time = 0

    def read_from_file(self):
        data = []
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)

        for day in [yesterday, today]:
            dir_name = day.strftime('%d.%m.%y')
            dir_path = self.dir_ + '/' + dir_name
            if not self.dir_patter.match(dir_name) or not os.path.isdir(dir_path):
                continue

            for file in sorted(os.listdir(dir_path)):
                file_path = dir_path + '/' + file
                if self.file_pattern.match(file) and os.path.isfile(file_path):
                    with np.load(file=file_path) as npz:
                        for item in npz['arr']:
                            data.append(item)
        return data

    def write_to_file(self, data):
        if not self.buffer:
            self.last_time = data['time']

        self.buffer.append(data)

        if data['time'] - self.last_time > self.writing_delta_time:
            today = datetime.date.today().strftime('%d.%m.%y')
            if not os.path.isdir(self.dir_ + '/' + today):
                os.mkdir(self.dir_ + '/' + today)

            now = datetime.datetime.now().strftime("%H_%M_%S.npz")
            np.savez_compressed(self.dir_ + '/' + today + '/' + now, arr=self.buffer)
            self.buffer.clear()


file_io = FileIO()
