import threading
from time import sleep


import epics


class EpicsReader(threading.Thread):

    def __init__(self, sleeping_time=1):
        threading.Thread.__init__(self, name='EpicsReader')
        self.sleeping_time = 10  # TODO: вынести в config
        self.PV = epics.PV('VEPP4:NEP0:e1_i-I')

    def read_current(self):
        return self.PV.get()

    def run(self):
        while True:
            print(self.read_current())
            sleep(self.sleeping_time)


epics_reader = EpicsReader()
epics_reader.start()
