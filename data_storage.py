import bisect
from math import log
import numpy_ringbuffer as ringbuffer
import numpy as np
from config import config
from threading import Lock
from depolarizer import depolarizer
import time


chunk = np.dtype([('time', np.float64),
                  ('x_online_l', np.float32), ('y_online_l', np.float32),
                  ('x_online_r', np.float32), ('y_online_r', np.float32),
                  ('x_cog_l', np.float32), ('y_cog_l', np.float32),
                  ('x_cog_r', np.float32), ('y_cog_r', np.float32),
                  ('x_online_asym', np.float32), ('y_online_asym', np.float32),
                  ('x_cog_asym', np.float32), ('y_cog_asym', np.float32),
                  ('counter_l', np.int32), ('counter_r', np.int32)])

lock = Lock()

names = ['time', 'depol_energy']

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
        self.start_time = None

    def add(self, chunk_):
        """

        :param chunk_: tuple of chunk parameters
        """

        with lock:
            self.data_.append(np.array(chunk_, dtype=chunk))     # TODO: проверить неубывание

        if self.start_time is None and len(self.data_) != 0:
            self.start_time = self.data_['time'][0]

    def get_mean_from(self, last_time, period):
        # print(f"Current len = {len(self.data_)}")  # TODO: разобраться с длиной

        points = {key: [] for key in names}
        t = time.time()

        with lock:
            if len(self.data_) == 0:
                return points, last_time

            last_elem = self.data_.pop()
            self.data_.append(last_elem)

            if last_time + period >= last_elem['time']:
                return points, last_time

            data_ = np.copy(self.data_)

        if last_time == 0:
            last_time = data_['time'][0]

        while last_time + period < data_['time'][-1]:

            left = bisect.bisect_right(data_['time'], last_time)
            right = bisect.bisect_right(data_['time'], last_time + period)

            last_time += period
            if left == right:
                continue

            data = data_[left:right]
            print(data['counter_l'])

            for type_ in ['_l', '_r']:
                name = 'rate' + type_
                events_amount = np.sum(data['counter' + type_])
                freq = np.sum(data['counter' + type_]) / period
                freq_error = events_amount**0.5 / period
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

            points['time'].append(last_time - period / 2 - self.start_time)

            # подшивка точки деполяризатора

            freq = depolarizer.find_closest_freq(last_time - period / 2)
            energy = depolarizer.frequency_to_energy(freq) if freq != 0 else 0
            points['depol_energy'].append("%.3f" % energy)

            # print(f"Time: {time.time() - t}")  # замер времени. Удалить.

        # print(time.time() - t)  # замер времени. Удалить.
        # print(f"{100 * len(self.data_) / self.data_.maxlen} %")

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
        self.hists_ = ringbuffer.RingBuffer(buffer_len, dtype=(np.int32, (self.X, self.Y)))

    def add_as_array(self, x_list, y_list):
        hist_ = np.zeros((self.X, self.Y), dtype=np.int32)
        for x, y in zip(x_list, y_list):
            r_x, r_y = round(x), round(y)
            if (0 <= r_x < self.X) and (0 <= r_y < self.Y):
                hist_[r_x, r_y] += 1
        self.hists_.append(hist_)

    def get_hist(self, left=0, right=None):
        right = self.buffer_len if right is None else min(right, self.buffer_len)
        left, right = int(left), int(right)

        if left > right:
            raise ValueError(f'left (={left}) >= right (={right})')

        return np.mean(self.hists_[left:right], axis=0).T  # TODO: проверить axis mean. Проверять на пустоту?

    def get_events_num(self):
        return np.sum(self.hists_)


data_storage_ = ChunkStorage(config.asym_buffer_len)
hist_storage_ = HistStorage(config.GEM_X, config.GEM_Y, config.hist_buffer_len)
