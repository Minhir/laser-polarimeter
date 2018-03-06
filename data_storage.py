import numpy_ringbuffer as ringbuffer
import numpy as np
from config import config
from threading import Lock
import time

from depolarizer import depolarizer

chunk = np.dtype([('time', np.float64), ('pol', np.int32),
                  ('x_online', np.float32), ('y_online', np.float32),
                  ('x_cog', np.float32), ('y_cog', np.float32)])  # ID, I_e, detector

lock = Lock()

a = []


class ChunkStorage:

    def __init__(self, buffer_len):
        """
        Хранит точки асимметрии

        :param buffer_len: кол-во хранимых точек
        """
        self.buffer_len = buffer_len
        self.data_ = ringbuffer.RingBuffer(self.buffer_len, dtype=chunk)

    def add(self, chunk_list):
        """

        :param chunk_list: (time, pol, x_online_, y_online, x_cog, y_cog)
        """

        with lock:
            for i in chunk_list:
                self.data_.append(np.array(i, dtype=chunk))

    def get(self):
        with lock:
            return np.array(self.data_)

    def get_from(self, index):
        """
        Выдаёт данные с места index. Считает index так, как если бы это не был
        циклический буффер.

        Пример: длина буфера 10, а мы записали 15 чисел 1..15, тогда реально
        в буфере находятся 6..15. Но по обращению к 15 мы получим 15 элемент.

        :return:
        """
        # TODO сделать аккуратно
        with lock:
            new_index = index % self.buffer_len
            if self.data_.is_full:
                if new_index <= self.data_._left_index:
                    return self.data_._arr[new_index:self.data_._left_index]
                else:
                    return np.concatenate((self.data_._arr[new_index:],
                                           self.data_._arr[:self.data_._left_index]))
            else:
                return self.data_[new_index:]

    def get_mean_from(self, last_time, period):
        points = {'x_online': [], 'y_online': [],
                  'online_error_lower': [], 'online_error_upper': [],
                  'time': [], 'depol_freq': []}

        with lock:

            if len(self.data_) == 0:
                return points, last_time

            if last_time == 0:
                last_time = np.min(self.data_['time'])

            t = time.time()
            while last_time + period < self.data_['time'][-1]:
                # TODO: избавиться от O(n). (а надо ли?)
                # ind_ = (last_time < self.data_['time']) & (self.data_['time'] < last_time + period)

                ind_ = np.abs(self.data_['time'] - last_time - period / 2) < period / 2
                len_ = np.sum(ind_)

                if len_ == 0:
                    last_time += period
                    continue

                y_mean = np.mean(self.data_['y_online'][ind_])
                y_std = np.std(self.data_['x_online'][ind_]) / len(self.data_['x_online'][ind_])**0.5
                points['x_online'].append(np.mean(self.data_['x_online'][ind_]))
                points['y_online'].append(y_mean)

                points['online_error_lower'].append(y_mean - y_std)
                points['online_error_upper'].append(y_mean + y_std)

                mean_time = np.mean(self.data_['time'][ind_])
                points['time'].append(mean_time)
                last_time = self.data_['time'][ind_][-1]

                # подшивка точки деполяризатора

                # if True:   # TODO спрашивать состояние деполяризатора
                #     def find_closest():
                #         closest = float('inf')
                #         key = -1
                #         for k in depolarizer.fmap.keys():
                #             if abs(k - mean_time) < closest:
                #                 closest = abs(k - mean_time)
                #                 key = k
                #         return key
                #
                #     points['depol_freq'].append(find_closest())
                #
                # else:
                #     points['depol_freq'].append(-1)
                points['depol_freq'].append(-1)
                # подшивка

            a.append(time.time() - t)
            print(np.mean(a))   # замер времени. Удалить.
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
        if right is None:
            right = self.buffer_len
        else:
            right = min(right, self.buffer_len)

        if left > right:
            raise ValueError(f'left (={left}) >= right (={right})')

        if len(self.hists_[left:right]):   # Проверка на пустоту
            mean_ = np.mean(self.hists_[left:right], axis=0)  # TODO: проверить axis mean
        else:
            mean_ = np.zeros((self.X, self.Y), dtype=np.int32)

        return mean_.T


data_storage_ = ChunkStorage(config.asym_buffer_len)
# x = np.array((1, 2, 3, 4, 5, 6), dtype=chunk)  # TODO разобраться с индексированием циклического буфера
# print(x)
# data_storage_.add(x)
# data_storage_.add(x)
# data_storage_.add(x)
# print(data_storage_.get()['time'])
# print(len(data_storage_.data_))
# print()
# print(data_storage_.data_)
# print()
# print(np.array(data_storage_.data_))
# print(data_storage_.data_._unwrap()[2])
# print(data_storage_.data_[0:1])
# print(data_storage_.data_[len(data_storage_.data_)])
hist_storage_ = HistStorage(config.GEM_X, config.GEM_Y, config.hist_buffer_len)
