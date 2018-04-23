import yaml


class Config:

    def __init__(self):
        """Хранитель конфигурации"""
        # TODO: добавить проверку конфигурационных значений

        with open('config.yaml', 'r') as config_file:
            try:
                _config = yaml.load(config_file)
                self.GEM_X = int(_config['GEM']['X'])
                self.GEM_Y = int(_config['GEM']['Y'])
                self.hist_buffer_len = int(_config['data']['hist_buffer_len'])
                self.asym_buffer_len = int(_config['data']['asym_buffer_len'])
                self.web_port = int(_config['web']['port'])
                self.ip_list = _config['web']['allowed_ip']
                self.GEM_slipping_time = float(_config['GEM']['call_period'])
                self.laser_freq = float(_config['laser']['freq'])
                self.depol_bounds = _config['depolarizer']['bounds']
                self.delta_time = float(_config['data']['delta_time'])
                self.writing_delta_time = float(_config['data']['writing_delta_time'])
                self.GEM_idle = bool(_config['debug']['idle_mod'])
                self.read_hitdump = bool(_config['debug']['read_hitdump'])
                self.hitdump_dir = _config['debug']['hitdump_dir']
                self.hitdump_mask = _config['debug']['hitdump_mask']
                for i in range(len(self.ip_list)):
                    #  Припишем номер порта к ip адресам
                    self.ip_list[i] += ':' + str(self.web_port)

            except yaml.YAMLError as exc:
                print("Ошибка конфигурации")
                print(exc)

            else:
                self.print_config()

    def print_config(self):
        print('Конфигурация:\n -- ', end='')
        print('\n -- '.join([f'GEM X = {self.GEM_X}',
                             f'GEM Y = {self.GEM_Y}',
                             f'Холостой режим' if self.GEM_idle else '',
                             f'Чтение hitdump' if self.read_hitdump else '',
                             f'Директория {self.hitdump_dir}' if self.read_hitdump else '',
                             f'Маска для файлов {self.hitdump_mask}' if self.read_hitdump else '',
                             f'Размер буфера гистограмм = {self.hist_buffer_len}',
                             f'Размер буфера точек = {self.asym_buffer_len}',
                             f'Время усреднения = {self.delta_time}',
                             f'Период сохранения данных на диск = {self.writing_delta_time}',
                             f'Ограничения настроек деполяризатора {self.depol_bounds}',
                             f'IP имеющие доступ: {self.ip_list}',
                             f'Период опроса детектора = {self.GEM_slipping_time}',
                             f'Частота лазера = {self.laser_freq}']), end="\n\n")


config = Config()
