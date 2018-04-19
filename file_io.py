import os
import datetime

import re
import numpy as np


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

        self.file = self._init_file()

    def _init_file(self):
        return open("test.txt", "a")

    def read_from_file(self):
        data = []
        today = datetime.date.today().strftime('%d.%m.%y')
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y_%m_%d')

        for dir_name in [yesterday, today]:
            dir_path = self.dir_ + '/' + dir_name
            if not self.dir_patter.match(dir_name) or not os.path.isdir(dir_path):
                continue

            for file in sorted(os.listdir(dir_path)):
                file_path = dir_path + '/' + file
                if self.file_pattern.match(file) and os.path.isfile(file_path):
                    with np.load(file=file_path) as npz:
                        print(npz.items())
                        data.append(npz['arr'])
        return data

    def write_to_file(self, data):
        today = datetime.date.today().strftime('%d.%m.%y')
        if not os.path.isdir(self.dir_ + '/' + today):
            os.mkdir(self.dir_ + '/' + today)

        now = datetime.datetime.now().strftime("%H_%M_%S.npz")
        np.savez_compressed(self.dir_ + '/' + today + '/' + now, arr=data)


file_io = FileIO()