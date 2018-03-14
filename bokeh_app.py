from bokeh.layouts import row, column, WidgetBox
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, Whisker, LinearAxis
from bokeh.models.widgets import RangeSlider, Slider, Div, Button, TextInput, Panel, Tabs

from math import pi
from data_storage import hist_storage_, data_storage_, names
from depolarizer import depolarizer
from config import config


def app(doc):

    # Гистограмма пятна
    img = hist_storage_.get_hist()
    hist_source = ColumnDataSource(data=dict(image=[img]))
    width_ = config.GEM_X * 5
    hist_height_ = config.GEM_Y * 5
    height_ = 300
    hist_fig = figure(plot_width=width_, plot_height=hist_height_,
                      x_range=(0, config.GEM_X), y_range=(0, config.GEM_Y))

    hist_fig.image(image='image', x=0, y=0, dw=config.GEM_X, dh=config.GEM_Y, palette="Spectral11", source=hist_source)

    hist_buffer_len = config.hist_buffer_len - 1
    hist_slider = RangeSlider(start=0, end=hist_buffer_len, value=(0, hist_buffer_len),
                              step=1, title="Срез пятна (от..до) сек назад")

    def hist_update():
        hist_source.data = {'image': [hist_storage_.get_hist(hist_buffer_len - hist_slider.value[1],
                                                             hist_buffer_len - hist_slider.value[0])]}  # TODO: починить

    # График асимметрии
    # TODO выделение точки

    asym_fig = figure(plot_width=width_, plot_height=height_) # , x_range=[0, 10], y_range=[0, 10])

    asym_source = ColumnDataSource({key: [] for key in names})

    # asym_fig.extra_x_ranges["depolarizer"] = FactorRange("c", 'f')
    asym_fig.extra_x_ranges["depolarizer"] = asym_fig.x_range  # Связал ось деполяризатора с осью времени

    asym_fig.add_layout(Whisker(source=asym_source, base="time",
                                upper="y_online_asym_up_error", lower="y_online_asym_down_error"))  # TODO: сделать усы

    asym_fig.add_layout(LinearAxis(x_range_name="depolarizer"), 'below')

    asym_fig.circle('time', 'y_online_asym', source=asym_source, size=8, color="black")

    asym_fig.yaxis[0].axis_label = "<Асимметрия по y [мм]"
    asym_fig.xaxis[0].axis_label = 'Время'
    asym_fig.xaxis[1].axis_label = 'Частота деполяризатора'
    asym_fig.xaxis[1].major_label_orientation = pi / 2  # 0.52
    depol_list = []
    asym_fig.xaxis[1].major_label_overrides = {}

    asym_slider = Slider(start=1, end=300, value=100, step=1, title="Время усреднения")
    params = {'last_time': 0, 'period': 1}

    # 'x_start': 10**10, 'x_end': 0}

    # def asym_plot(points):

    def asym_update():

        if params['period'] != asym_slider.value:
            asym_source.data = {name: [] for name in names}
            params['period'] = asym_slider.value
            params['last_time'] = 0
            # asym_fig.xaxis[1].ticker.ticks.clear()
            depol_list.clear()

        points, params['last_time'] = data_storage_.get_mean_from(params['last_time'], params['period'])

        for i, time in enumerate(points['time']):
            if points['depol_freq'][i] == "0.000":
                continue
            asym_fig.xaxis[1].major_label_overrides[time] = points['depol_freq'][i]
            depol_list.append(time)

        asym_fig.xaxis[1].ticker = depol_list       # TODO: поменять
        asym_source.stream(points, rollover=10000)
        # doc.add_next_tick_callback(partial(asym_plot, points))

    # Настраиваемы график

    fig_names = ["y_online"]
    fig_handler = []

    for fig_name in fig_names:
        for type_ in ['_l', '_r']:
            fig = figure(plot_width=width_, plot_height=height_)

            fig.add_layout(Whisker(source=asym_source, base="time",
                                   upper=fig_name + type_ + '_up_error',
                                   lower=fig_name + type_ + '_down_error'))

            fig.circle('time', fig_name + type_, source=asym_source, size=8, color="black")
            fig.yaxis[0].axis_label = f"<{fig_name + type_}> [мм]"
            fig.xaxis[0].axis_label = 'Время'

            fig_handler.append((fig, fig_name + type_))

    # Вкладки графика
    tab1 = Panel(child=asym_fig, title="Y")
    tabs = []
    for fig, fig_name in fig_handler:
        tabs.append(Panel(child=fig, title=fig_name))

    tab_handler = Tabs(tabs=tabs)

    # Окно статуса деполяризатора

    # TODO: часы

    depol_status_window = Div(text="""Статус деполяризатора.
    Выключен""",
              width=200, height=100)

    depol_button_start = Button(label="Включить сканирование", width=200)
    depol_button_stop = Button(label="Выключить сканирование", width=200)

    depol_input_speed = TextInput(value=str(depolarizer.get_speed()), title="Скорость:")
    depol_input_step = TextInput(value=str(depolarizer.get_step()), title="Шаг:")
    depol_input_initial = TextInput(value=str(depolarizer.get_initial()), title="Начало:")
    depol_input_final = TextInput(value=str(depolarizer.get_final()), title="Конец:")

    def update_depol_status():
        if depolarizer.is_scan():
            depol_button_start .button_type = "success"
            depol_button_stop.button_type = "danger"
        else:
            depol_button_start .button_type = "danger"
            depol_button_stop.button_type = "success"

        try:
            depol_speed = float(depol_input_speed.value)    # TODO: добавить проверку. Обновлять значние. Раз в секунду.

            if abs(depol_speed) < 1000:
                depolarizer.set_speed(depol_speed)
            else:
                raise ValueError("Некорректное значение скорости")

            depol_step = float(depol_input_step.value)
            depolarizer.set_step(depol_step)

            depol_init = float(depol_input_initial.value)
            depolarizer.set_initial(depol_init)

            depol_final = float(depol_input_final.value)
            depolarizer.set_final(depol_final)

        except ValueError as e:
            print(e)

    def start_scan():
        depolarizer.start_scan()

    def stop_scan():
        depolarizer.stop_scan()

    depol_button_start.on_click(start_scan)
    depol_button_stop.on_click(stop_scan)

    # Инициализация bokeh app
    column_1 = column(tab_handler, asym_fig, asym_slider, width=width_ + 50)
    widgets_ = WidgetBox(depol_button_start, depol_button_stop)
    column_2 = column(hist_fig, hist_slider, widgets_, depol_input_speed,
                      depol_input_step, depol_input_initial, depol_input_final, depol_status_window)
    layout_ = row(column_1, column_2)

    doc.add_root(layout_)
    doc.add_periodic_callback(hist_update, 1000)         # TODO запихнуть в один callback
    doc.add_periodic_callback(asym_update, 1000)         # TODO: подобрать периоды
    doc.add_periodic_callback(update_depol_status, 1000)
    doc.title = "Laser polarimeter"
