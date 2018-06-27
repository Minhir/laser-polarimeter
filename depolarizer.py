from Message_pb2 import *
import socket
import struct
import time
from threading import Thread, Lock
import bisect


# some helper function to send and receive message

lock_receive = Lock()
lock_send = Lock()


def send(sock, message):
    message.timestamp = int(time.time()*1e9)
    sock.send(struct.pack('I', message.ByteSize()))
    sock.send(message.SerializeToString())


def receive(sock):
    while True:
        try:
            data = sock.recv(4)
            s = struct.unpack('I', data)
            data = sock.recv(s[0])
            m = Message()
            m.ParseFromString(data)
            return m
        except google.protobuf.message.DecodeError: pass

class Depolarizer:

    def __init__(self, host, port, freq_storage_=None):
        self.host = host
        self.port = port
        self.sock = socket.socket()
        self.sock.connect((host, port))
        self.freq_storage_ = freq_storage_
        self.fmap_thread = None
        self.update_thread = None
        self.message_id = 0
        self.is_fmap = False
        self.fmap = []
        self._RD = 440.6484586602595
        self._F0 = 818924.144144

        self.attenuation = self.get_attenuation()
        self.harmonic_number = self.get_harmonic_number()
        self.final = self.get_final()
        self.final_energy = self.frequency_to_energy(self.final)
        self.initial = self.get_initial()
        self.initial_energy = self.frequency_to_energy(self.initial)
        self.is_scan = self.get_is_scan()
        self.speed = self.get_speed()
        self.step = self.get_step()
        self.revolution_frequency = self.get_revolution_frequency()
        self.state = self.get_state()
        self.current_frequency = self.get_current_frequency()
        if self.current_frequency == 0:
            self.current_energy = 0
        else:
            self.current_energy =self.frequency_to_energy(self.current_frequency)

    def send(self, message):
        with lock_send:
            send(self.sock, message)

    def receive(self):
        with lock_receive:
            return receive(self.sock)

    def do(self, command):
        m = Message()
        m.id = self.message_id
        self.message_id = self.message_id + 1
        m.command = command
        self.send(m)
        m = self.receive()
        return m.status == Message.OK

    def start_scan(self):
        self.is_scan = True
        return self.do(Message.START)

    def stop_scan(self):
        self.is_scan = False
        return self.do(Message.STOP)

    def continue_scan(self):
        return self.do(Message.CONTINUE)

    def get(self, data_type):
        m = Message()
        m.id = self.message_id
        self.message_id = self.message_id + 1
        m.command = Message.GET
        m.data_type = data_type
        self.send(m)
        m = self.receive()
        return m.data

    def set(self, data_type, data):
        m = Message()
        m.id = self.message_id
        self.message_id += 1
        m.command = Message.SET
        m.data_type = data_type
        m.data = data
        self.send(m)
        m = self.receive()
        return m.data

    def get_state(self):
        self.state = self.get(Message.STATE)
        return self.state

    def is_off(self):
        state = self.get_state()
        return not (state == Message.ON or state == Message.SCAN)

    def is_on(self):
        state = self.get_state()
        return state == Message.ON or state == Message.SCAN

    def get_is_scan(self):
        self.is_scan = (self.get_state() == Message.SCAN)
        return self.is_scan

    def get_initial(self):
        self.initial = self.get(Message.INITIAL)
        self.initial_energy = self.frequency_to_energy(self.initial)
        return self.initial

    def get_final(self):
        self.final = self.get(Message.FINAL)
        self.final_energy = self.frequency_to_energy(self.final)
        return self.final
      
    def get_step(self):
        self.step = self.get(Message.STEP)
        return self.step

    def get_speed(self):
        self.speed = self.get(Message.SPEED)
        return self.speed

    def get_attenuation(self):
        self.attenuation = self.get(Message.ATTENUATION)
        return self.attenuation

    def get_current_frequency(self):
        self.current_frequency = self.get(Message.CURRENT)
        return self.current_frequency

    def get_harmonic_number(self):
        self.harmonic_number = self.get(Message.HARMONIC_NUMBER)
        return self.harmonic_number

    def get_revolution_frequency(self):
        self.revolution_frequency = self.get(Message.REVOLUTION_FREQUENCY)
        return self.revolution_frequency
    
    def get_generator(self):
        m = Message()
        m.id = self.message_id
        self.message_id = self.message_id + 1
        m.command = Message.GET
        m.data_type = Message.GENERATOR
        self.send(m)
        m = self.receive()
        return m.comment

    def set_initial(self, data):
        self.initial = data
        self.initial_energy = self.frequency_to_energy(self.initial)
        return self.set(Message.INITIAL, self.initial)

    def set_initial_energy(self, data):
        self.initial_energy = data
        self.initial = self.energy_to_frequency(data)
        return self.set(Message.INITIAL, self.initial)

    def set_final(self, data):
        self.final = data
        self.final_energy = self.frequency_to_energy(self.final)
        return self.set(Message.FINAL, self.final)

    def set_final_energy(self, data):
        self.final_energy = data
        self.final = self.energy_to_frequency(data)
        return self.set(Message.FINAL, self.final)

    def set_step(self, data):
        self.step = data
        return self.set(Message.STEP, data)

    def set_speed(self, data):
        self.speed = data
        return self.set(Message.SPEED, data)

    def set_attenuation(self, data):
        self.attenuation = data
        return self.set(Message.ATTENUATION, data)

    def set_harmonic_number(self, data):
        self.harmonic_number = data
        self.set_initial(self.energy_to_frequency(self.initial_energy))
        self.set_final(self.energy_to_frequency(self.final_energy))
        return self.set(Message.HARMONIC_NUMBER, data)

    def set_revolution_frequency(self, data):
        self.revolution_frequency = data
        return self.set(Message.REVOLUTION_FREQUENCY, data)

    def set_generator(self, generator):
        m = Message()
        m.id = self.message_id
        self.message_id += 1
        m.command = Message.SET
        m.data_type = Message.GENERATOR
        m.comment = generator
        self.send(m)
        m = self.receive()
        return m.comment

    def get_fmap_in_thread(self):
        sock = socket.socket()
        sock.connect((self.host, self.port))
        m = Message()
        mid = 0
        m.id = mid
        m.command = Message.GET
        m.data_type = Message.FMAP
        send(sock, m)
        m = receive(sock)
        if m.status == Message.OK:
            while self.is_fmap:
                m = receive(sock)
                for fm in m.fmap.frequency:
                    if self.freq_storage_ is not None:
                        self.freq_storage_.add(fm.timestamp*1e-9, fm.frequency)
                    else:
                        self.fmap.append((fm.timestamp*1e-9, fm.frequency))
        self.is_fmap = False

    def start_fmap(self):
        if not self.is_fmap:
            self.is_fmap = True
            self.fmap_thread = Thread(target=self.get_fmap_in_thread, args=(), name='fmap update')
            self.fmap_thread.daemon = True
            self.fmap_thread.start()
            print("fmap tread started")

    def stop_fmap(self):
        if self.fmap_thread is None:
            print("Fmap thread not started!")
        self.is_fmap = False
        self.fmap_thread.join()

    def clear_fmap(self):
        self.fmap.clear()

    def print_fmap(self):
        for time_, freq in self.fmap:
            print(time_, "   ", freq)

    def frequency_to_energy(self, f, f0=None, n=None):  #  TODO: сделать функцию static чтобы работала при отключенном деполяризаторе
        if f0 is None:
            f0 = self._F0
        if n is None:
            n = self.harmonic_number
        return (f / f0 + n) * self._RD

    def energy_to_frequency(self, E, f0=None, n=None):
        if f0 is None:
            f0 = self._F0
        if n is None:
            n = self.harmonic_number
        return (E / self._RD - n) * f0

    def find_closest_freq(self, time_):
        ind = bisect.bisect_right(self.fmap,
                                  (time_, 0),
                                  lo=0, hi=len(self.fmap)) - 1
        if ind == -1:
            return 0

        return self.fmap[ind][1]

    def update_status(self):
        while True:
            time.sleep(1)
            # self.attenuation = self.get_attenuation()
            # self.final = self.get_final()
            # self.initial = self.get_initial()
            # self.speed = self.get_speed()
            # self.harmonic_number = self.get_harmonic_number()
            # self.step = self.get_step()
            # self.revolution_frequency = self.get_revolution_frequency()
            # self.state = self.get_state()
            self.get_is_scan()
            self.get_current_frequency()
            if self.current_frequency == 0:
                self.current_energy = 0
            else:
                self.current_energy = self.frequency_to_energy(self.current_frequency)

    def get_by_name(self, name):
        if name in self.__dict__:
            return self.__dict__[name]
        else:
            return None

    def start_update(self):
        if self.update_thread is None:
            self.update_thread = Thread(target=self.update_status, name='depol status update')
            self.update_thread.daemon = True
            self.update_thread.start()


class MayBeCalled(object):
    def __call__(self, *args, **kwargs):
        return 0


class FakeDepolarizer:

    def __getattr__(self, attr):
        if attr in ["speed", "step", "initial", "final", "harmonic_number", "attenuation",
                    "is_scan", "current_frequency"]:
            return 0
        elif attr == "fmap":
            return []
        elif attr == "frequency_to_energy":
            def frequency_to_energy(f, f0=None, n=None):  # TODO: костыль, убрать отсюда
                if f0 is None:
                    f0 = 818924.144144
                if n is None:
                    n = 9  # TODO: писать n в таблицу на жесткий диск!
                return (f / f0 + n) * 440.6484586602595
            return frequency_to_energy

        return MayBeCalled()

    def __setattr__(self, attr, *val):
        pass
