from Message_pb2 import *
import socket
import struct
import time
from threading import Thread

# some helper function to send and receive message


def send(sock, message):
    message.timestamp = int(time.time()*1e9)
    sock.send(struct.pack('I',message.ByteSize()))
    sock.send(message.SerializeToString())


def receive(sock):
    data = sock.recv(4)
    s = struct.unpack('I',data)
    #print "message size = ",s[0]
    data = sock.recv(s[0])
    m = Message()
    m.ParseFromString(data)
    return m


class Depolarizer:

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = socket.socket()
        self.sock.connect((host, port))
        self.message_id = 0
        self.is_fmap = False
        self.fmap = {}

    def send(self, message):
        send(self.sock, message)

    def receive(self):
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
        return self.do(Message.START)

    def stop_scan(self):
        return self.do(Message.STOP)

    def continue_scan(self):
        return self.do(Message.CONTINUE)

    def get(self,data_type):
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
      return self.get(Message.STATE)

    def is_off(self):
      return  not (self.get_state() == Message.ON or self.get_state() == Message.SCAN)

    def is_on(self):
      return self.get_state() == Message.ON or self.get_state() == Message.SCAN

    def is_scan(self):
      return self.get_state() == Message.SCAN
      

    def get_initial(self):
        return self.get(Message.INITIAL)

    def get_final(self):
        return self.get(Message.FINAL)
      
    def get_step(self):
        return self.get(Message.STEP)

    def get_speed(self):
        return self.get(Message.SPEED)

    def get_attenuation(self):
        return self.get(Message.ATTENUATION)

    def get_harmonic_number(self):
        return self.get(Message.HARMONIC_NUMBER)

    def get_revolution_frequency(self):
        return self.get(Message.REVOLUTION_FREQUENCY)

    def set_initial(self, data):
        return self.set(Message.INITIAL, data)

    def set_final(self, data):
        return self.set(Message.FINAL, data)
      
    def set_step(self, data):
        return self.set(Message.STEP, data)

    def set_speed(self, data):
        return self.set(Message.SPEED, data)

    def set_attenuation(self, data):
        return self.set(Message.ATTENUATION,data)

    def set_harmonic_number(self, data):
        return self.set(Message.HARMONIC_NUMBER,data)

    def set_revolution_frequency(self, data):
        return self.set(Message.REVOLUTION_FREQUENCY,data)

    def get_fmap_in_thread(self):
        sock = socket.socket()
        sock.connect((self.host, self.port))
        m = Message()
        mid = 0
        m.id = mid
        m.command = Message.GET
        m.data_type = Message.FMAP
        send(sock,m)
        m = receive(sock)
        if m.status == Message.OK:
            while self.is_fmap:
                m = receive(sock)
                for fm in m.fmap.frequency:
                    self.fmap[fm.timestamp] = fm.frequency
        self.is_fmap = False

    def start_fmap(self):
        if not self.is_fmap:
            self.is_fmap = True
            self.fmap_thread = Thread(target=self.get_fmap_in_thread, args=())
            self.fmap_thread.start()
            print("fmap tread started")

    def stop_fmap(self):
        self.is_fmap = False
        self.fmap_thread.join()

    def clear_fmap(self):
        self.fmap = {}

    def print_fmap(self):
        for t in sorted(self.fmap):
            print(str(t) + str(self.fmap[t]))


depolarizer = Depolarizer('192.168.176.61', 9090)
