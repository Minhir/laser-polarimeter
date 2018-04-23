import re
import os

from config import config


class HItStruct:

    def __init__(self, time=-1, pol=-1, x=-1, y=-1):
        self.x_online = x
        self.y_online = y
        self.x_cog = x
        self.y_cog = y
        self.charge = 0
        self.timestamp = time
        self.polarity = pol


def read_hitdump():
    dir_ = config.hitdump_dir
    file_pattern = re.compile(config.hitdump_mask)
    data = []

    if not os.path.isdir(dir_):
        print(f'Не могу найти директорию {dir_}')
        return data

    for file in sorted(os.listdir(dir_)):
        file_path = dir_ + '/' + file
        if file_pattern.match(file) and os.path.isfile(file_path):
            print(f'Read {file_path}...')
            with open(file_path) as file:
                for line in file.readlines():
                    time, _, det_number, pol, x, y, *_ = map(float, line.split())
                    if det_number == 2:
                        data.append(HItStruct(time=time, pol=int(pol), x=x, y=y))
    print('Stop reading')
    return data
