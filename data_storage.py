import bisect
from math import log, floor
from threading import Lock
import time

import numpy_ringbuffer as ringbuffer
import numpy as np

from config import config
from depolarizer import depolarizer
from file_io import file_io

chunk = np.dtype([('time', np.float64),
                  ('x_online_l', np.float32), ('y_online_l', np.float32),
                  ('x_online_r', np.float32), ('y_online_r', np.float32),
                  ('x_cog_l', np.float32), ('y_cog_l', np.float32),
                  ('x_cog_r', np.float32), ('y_cog_r', np.float32),
                  ('x_online_asym', np.float32), ('y_online_asym', np.float32),
                  ('x_cog_asym', np.float32), ('y_cog_asym', np.float32),
                  ('counter_l', np.float32), ('counter_r', np.float32),
                  ('charge', np.float32)])

lock = Lock()

names = ['time', 'depol_energy', 'charge']

for rate in ['rate', 'corrected_rate']:
    for type_ in ['_l', '_r']:
        for error_ in ['', '_up_error', '_down_error']:
            names.append(rate + type_ + error_)

for axis in ['x_', 'y_']:
    for reco in ['online_', 'cog_']:
        for type_ in ['l', 'r', 'asym']:
            for error_ in ['', '_up_error', '_down_error']:
                names.append(axis + reco + type_ + error_)


class ChunkStorage:

    def __init__(self, buffer_len):
        """
        Хранит точки асимметрии

        :param buffer_len: кол-во хранимых точек
        """
        self.buffer_len = buffer_len
        self.data_ = ringbuffer.RingBuffer(self.buffer_len, dtype=chunk)
        self.time_data_ = ringbuffer.RingBuffer(self.buffer_len)  # Аналог self.data_['time'], только в np.array.
        self.start_time = None  # TODO: Отвязаться от локального времени
        if not config.read_hitdump:
            self._read_from_files()
        # self._test_full()

    def _test_full(self):
        st = self.data_[0]
        for i in range(self.buffer_len):
            self.data_.append(st)

    def _read_from_files(self):
        for data in file_io.read_from_file():
            self.data_.append(data)
            self.time_data_.append(data['time'])

    def add(self, chunk_):
        """

        :param chunk_: tuple of chunk parameters
        """

        data = np.array(chunk_, dtype=chunk)
        with lock:
            self.data_.append(data)  # TODO: проверить неубывание
            self.time_data_.append(data['time'])

        if not config.read_hitdump:
            file_io.write_to_file(data)

        if self.start_time is None and len(self.data_) != 0:
            self.start_time = self.time_data_[0]

    def get_mean_from(self, last_time, period):
        points = {key: [] for key in names}
        t = time.time()

        with lock:
            if len(self.data_) == 0:
                return points, last_time

            last_data_time = self.time_data_.pop()
            self.time_data_.append(last_data_time)

            if last_time + period >= last_data_time:
                return points, last_time

            ind = bisect.bisect_right(self.time_data_, last_time)

            # print(f"A time = {time.time() - t}")

            data_ = self.data_[ind:]        # TODO: Убрать лишнее копирование
            time_data_ = self.time_data_[ind:]

            # print(f"C time = {time.time() - t}")

        if last_time == 0:
            last_time = time_data_[0]

        while last_time + period < data_['time'][-1]:

            left = bisect.bisect_right(time_data_, last_time)
            right = bisect.bisect_right(time_data_, last_time + period)

            last_time += period
            if left == right:
                continue

            data = data_[left:right]

            for type_ in ['_l', '_r']:
                name = 'rate' + type_
                freq = np.sum(data['counter' + type_]) / period
                freq_error = (freq / period * (1 - 2 * freq / config.laser_freq)) ** 0.5
                points[name].append(freq)
                points[name + '_down_error'].append(freq - freq_error)
                points[name + '_up_error'].append(freq + freq_error)

                try:
                    corrected_rate = - config.laser_freq / 2 * log(1 - freq / config.laser_freq * 2)
                    corrected_rate_error = freq_error / (1 - freq / config.laser_freq * 2)
                except:
                    corrected_rate = 0
                    corrected_rate_error = 0
                points['corrected_rate' + type_].append(corrected_rate)
                points['corrected_rate' + type_ + '_down_error'].append(corrected_rate - corrected_rate_error)
                points['corrected_rate' + type_ + '_up_error'].append(corrected_rate + corrected_rate_error)

            for axis in ['x_', 'y_']:
                for reco in ['online_', 'cog_']:
                    for type_ in ['l', 'r', 'asym']:
                        name = axis + reco + type_
                        mean = np.mean(data[name])
                        error = np.std(data[name]) / (right - left) ** 0.5
                        points[name].append(mean)
                        points[name + '_down_error'].append(mean - error)
                        points[name + '_up_error'].append(mean + error)
            # points['time'].append(last_time - period / 2 - self.start_time)
            points['time'].append((last_time - period / 2) * 10**3)
            points['charge'].append(np.mean(data['charge']))

            # подшивка точки деполяризатора

            freq = depolarizer.find_closest_freq((last_time - period / 2))
            energy = depolarizer.frequency_to_energy(freq) if freq != 0 else 0
            points['depol_energy'].append("%.3f" % energy)

        # print(f"time per step = {time.time() - t}")  # замер времени. Удалить.
        # print(f"{100 * len(self.data_) / self.data_.maxlen} %")
        # print()

        # ~ 50 %, 50 мс
        # перешёл на хранение 500_000
        # 40%, 26 мс
        # добавил отдельно массив времени
        # 50%, 6 мс
        return points, last_time


class HistStorage:

    def __init__(self, X, Y, buffer_len):
        """
        Хранит гистограммы (пятно) с детектора

        :param X: количество шагов гистограммы по X
        :param Y: количество шагов гистограммы по Y
        :param buffer_len: кол-во хранимых гистограмм
        """

        self.buffer_len = buffer_len
        self.X = X
        self.Y = Y
        self.x_arr = np.arange(self.X)
        self.y_arr = np.arange(self.Y)
        self.hists_ = ringbuffer.RingBuffer(buffer_len, dtype=(np.int32, (self.X, self.Y)))

    def add_as_GEM_struct_array(self, data):
        """
        Добавляет гистограмму в хранилище

        :param data: данные в виде hit_struct (GEM.h)
        """
        hist_ = np.zeros((self.X, self.Y), dtype=np.int32)
        for struct in data:
            r_x, r_y = floor(struct.x_online), floor(struct.y_online)
            if (0 <= r_x < self.X) and (0 <= r_y < self.Y):
                hist_[r_x, r_y] += 1
        self.hists_.append(hist_)

    def get_hist_with_std(self, left=0, right=None):
        """
        Возвращет усреднённую по срезу от left до right гистограмму

        :param left: от
        :param right: до
        :return: mean_hist, x_std, y_std -- усреднённая гистограмма, std вдоль x, std вдоль y
        """
        right = self.buffer_len if right is None else min(right, self.buffer_len)
        left, right = int(left), int(right)

        if left > right:
            raise ValueError(f'left (={left}) >= right (={right})')

        hists_ = self.hists_[left:right]

        if hists_.size != 0:
            mean_hist = np.nan_to_num(np.mean(hists_, axis=0).T)
        else:
            mean_hist = np.zeros((self.Y, self.X), dtype=np.int32)

        x = np.sum(mean_hist, axis=0).reshape(self.X)
        y = np.sum(mean_hist, axis=1).reshape(self.Y)

        if np.sum(x) == 0:
            x_std = 0
        else:
            x_average = np.average(self.x_arr, weights=x)
            x_std = np.average((self.x_arr - x_average) ** 2, weights=x) ** 0.5,

        if np.sum(y) == 0:
            y_std = 0
        else:
            y_average = np.average(self.y_arr, weights=y)
            y_std = np.average((self.y_arr - y_average) ** 2, weights=y) ** 0.5

        return mean_hist, x_std, y_std

    def get_events_sum(self):
        """Возвращает количество событий"""
        return np.sum(self.hists_)


data_storage_ = ChunkStorage(config.asym_buffer_len)
hist_storage_ = HistStorage(config.GEM_X, config.GEM_Y, config.hist_buffer_len)
