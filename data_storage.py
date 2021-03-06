import bisect
from math import log, floor, hypot
from threading import Lock

import numpy_ringbuffer as ringbuffer
import numpy as np
import bottleneck as bn

from config import config
from file_io import file_io

chunk = np.dtype([('time', np.float64),
                  ('x_one_l', np.float32), ('y_one_l', np.float32),
                  ('x_one_r', np.float32), ('y_one_r', np.float32),
                  ('x_cog_l', np.float32), ('y_cog_l', np.float32),
                  ('x_cog_r', np.float32), ('y_cog_r', np.float32),
                  ('x_one_asym', np.float32), ('y_one_asym', np.float32),
                  ('x_cog_asym', np.float32), ('y_cog_asym', np.float32),
                  ('counter_l', np.float32), ('counter_r', np.float32),
                  ('charge', np.float32)])      # TODO: добавить частоту, ослбаление [дБ]


names = ['time', 'depol_energy', 'charge', 'delta_rate', 'delta_rate_up_error', 'delta_rate_down_error']

for rate in ['rate', 'corrected_rate']:
    for type_ in ['_l', '_r']:
        for error_ in ['', '_up_error', '_down_error']:
            names.append(rate + type_ + error_)

x_y_names = []

for axis in ['x_', 'y_']:
    for reco in ['one_', 'cog_']:
        for type_ in ['l', 'r', 'asym']:
            x_y_names.append(axis + reco + type_)
            for error_ in ['', '_up_error', '_down_error', '_error']:
                names.append(axis + reco + type_ + error_)


def get_init_data():
    """Читает данные из файлов"""
    if not config.read_hitdump:
        print("Читаю старые данные...")
        init_data = file_io.read_from_file()
        print("Данные прочитаны")
    else:
        init_data = {}
    return init_data


class FreqMap:

    def __init__(self, buffer_len, init_data):
        """
        Хранит карту частот

        :param buffer_len: кол-во хранимых точек
        :param init_data: данные для инициализации
        """
        self.buffer_len = buffer_len
        self.freq_data_ = ringbuffer.RingBuffer(self.buffer_len)
        self.time_data_ = ringbuffer.RingBuffer(self.buffer_len)
        if 'depol_data' in init_data:
            for data in init_data['depol_data']:
                self.freq_data_.append(data['freq'])
                self.time_data_.append(data['time'])
        self.lock = Lock()

    def add(self, time_, freq_):

        with self.lock:
            self.freq_data_.append(freq_)
            self.time_data_.append(time_)

        file_io.add_freq_data(time_, freq_)

    def find_closest_freq(self, time_):
        with self.lock:
            ind = bisect.bisect_right(self.time_data_, time_)
        return 0 if ind == -1 else self.freq_data_[ind]


class ChunkStorage:

    def __init__(self, buffer_len, init_data, depolarizer, freq_storage_):
        """
        Хранит точки асимметрии

        :param buffer_len: кол-во хранимых точек
        :param init_data: данные для инициализации
        :param depolarizer: экземпляр деполяризатора
        :param freq_storage_: экземпляр freq_storage_
        """
        self.buffer_len = buffer_len
        self.lock = Lock()
        self.data_ = ringbuffer.RingBuffer(self.buffer_len, dtype=chunk)
        self.time_data_ = ringbuffer.RingBuffer(self.buffer_len)  # Аналог self.data_['time'], только в np.array.
        self.depolarizer = depolarizer
        self.freq_storage_ = freq_storage_
        if 'asym_data' in init_data:
            for data in init_data['asym_data']:
                self.data_.append(data)
                self.time_data_.append(data['time'])

    def add(self, chunk_):
        """

        :param chunk_: tuple of chunk parameters
        """

        data = np.array(chunk_, dtype=chunk)
        with self.lock:
            self.data_.append(data)
            self.time_data_.append(data['time'])

        if not config.read_hitdump:
            file_io.add_chunk_data(data)

    def get_mean_from(self, time_from, period, time_to=None) -> (list, float):
        """
        Возвращает данные начиная со времени time_from до времени time_to,
        усредненные по периоду period.

        :param time_from: при 0 берёт данные с самых малых времён (сек)
        :param period: период усреднения (сек)
        :param time_to: при None считает до самого большого времени (сек)
        :return: points, time_from -- список с усреднёнными данными,
                 метка времени, на которой закончилось усреднение
        """
        points = {key: [] for key in names}

        with self.lock:
            if len(self.data_) == 0:
                return points, time_from

            last_data_time = self.time_data_.pop()
            self.time_data_.append(last_data_time)

            if time_to is not None:
                last_data_time = time_to

            if time_from + period >= last_data_time:
                return points, time_from

            # Быстро (O(log N)) находит индекс элемента начиная с которого все больше time_from,
            ind = bisect.bisect_right(self.time_data_, time_from)

            data_ = self.data_[ind:]        # TODO: Убрать лишнее копирование
            time_data_ = self.time_data_[ind:]

        if time_from == 0:
            time_from = time_data_[0]

        while time_from + period < last_data_time:
            
            # Находит левый и правые индексы элементов между time_from и time_from + period
            left_ind = bisect.bisect_right(time_data_, time_from)
            right_ind = bisect.bisect_right(time_data_, time_from + period, lo=left_ind)
            data_len = right_ind - left_ind

            time_from += period
            if data_len == 0:
                continue

            # Копирует нужный интервал данных один раз, иначе каждое обращение к срезу -- копирование.
            data = data_[left_ind:right_ind]

            # Подсчет разных характеристик для интервала, формирование точки
            for type_ in ['_l', '_r']:
                name = 'rate' + type_
                freq = data['counter' + type_].sum() / period
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

            delta_rate = points['corrected_rate_l'][-1] - points['corrected_rate_r'][-1]
            delta_rate_error = hypot(points['corrected_rate_l_up_error'][-1] - points['corrected_rate_l'][-1],
                                     points['corrected_rate_r_up_error'][-1] - points['corrected_rate_r'][-1])
            points['delta_rate'].append(delta_rate)
            points['delta_rate_up_error'].append(delta_rate + delta_rate_error)
            points['delta_rate_down_error'].append(delta_rate - delta_rate_error)

            for name in x_y_names:
                data_len_ = data_len - np.isnan(data[name]).sum()  # Вычел из длины количество nan'ов
                mean = bn.nanmean(data[name])
                error = bn.nanstd(data[name]) / (data_len_**0.5)
                points[name].append(mean)
                points[name + '_down_error'].append(mean - error)
                points[name + '_up_error'].append(mean + error)
                points[name + '_error'].append(error)

            points['time'].append(time_from - period / 2)
            points['charge'].append(data['charge'].mean())

            # подшивка точки деполяризатора

            freq = self.freq_storage_.find_closest_freq(time_from - period / 2)
            energy = self.depolarizer.frequency_to_energy(freq) if freq != 0 else 0
            points['depol_energy'].append(round(energy, 3))

        return points, time_from


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
