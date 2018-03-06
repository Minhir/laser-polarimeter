import socket
import threading
from time import sleep
from data_storage import data_storage_


class Server (threading.Thread):
    def __init__(self, host, port):
        threading.Thread.__init__(self)
        self.host = host
        self.port = port
        self.sock = socket.socket()
        try:
            self.sock.connect((host, port))
        except :  # TODO: переделать
            print("Нет соединения с " + self.host + " " + str(self.port))
        self.message_id = 0
        self.is_fmap = False
        self.fmap = {}

    def receive(self):
        data = self.sock.recv(17)  # TODO: подумать над размером буфера
        try:
            x, y = map(float, data.split())
            # data_storage_.add_x(x)
            # data_storage_.add_y(y)
            print(len(data_storage_.data_x))
        except ValueError:
            print('Value error: can\'t read data from effect finder')


        # s = struct.unpack("ff", data)
        # print(sys.getsizeof(data))
        # print "message size = ",s[0]
        # data = self.sock.recv(s[0])

    def run(self):
        while True:
            self.receive()
            #sleep(0.5)  # Необязателен
