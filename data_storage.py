import bisect
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
                  ('x_cog_asym', np.float32), ('y_cog_asym', np.float32)])

lock = Lock()

names = ['time', 'depol_freq']

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

            if left == right:
                last_time += period
                continue

            data = data_[left:right]
            last_time = data['time'][-1]

            def make_point(name):
                mean = np.mean(data[name])
                error = np.std(data[name]) / (right - left)**0.5
                points[name].append(mean)
                points[name + '_down_error'].append(mean - error)
                points[name + '_up_error'].append(mean + error)

            for axis in ['x_', 'y_']:
                for reco in ['online_', 'cog_']:
                    for type_ in ['l', 'r', 'asym']:
                        make_point(axis + reco + type_)

            mean_time = np.mean(data['time'])
            points['time'].append(mean_time - self.start_time)

            # подшивка точки деполяризатора

            def find_closest():
                ind = bisect.bisect_right(depolarizer.fmap,
                                          (mean_time, 0),
                                          lo=0, hi=len(depolarizer.fmap)) - 1
                if ind == -1:
                    return 0

                freq = depolarizer.fmap[ind][1]
                if freq != 0:
                    return depolarizer.frequency_to_energy(freq, depolarizer._F0, depolarizer.harmonic_number)
                else:
                    return 0

            points['depol_freq'].append("%.3f" % find_closest())

            # print(f"Time: {time.time() - t}")  # замер времени. Удалить.
            # подшивка точки деполяризатора

        print(time.time() - t)  # замер времени. Удалить.
        print(f"{100 * len(self.data_) / self.data_.maxlen} %")

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
hist_storage_ = HistStorage(config.GEM_X, config.GEM_Y, config.hist_buffer_len)
