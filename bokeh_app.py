from functools import partial

from bokeh.layouts import row, column, layout
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, Whisker, Range1d, CategoricalAxis, FactorRange, LinearAxis
from bokeh.models.widgets import RangeSlider, Slider, Div, Button

import numpy as np
from tornado import gen

from data_storage import hist_storage_, data_storage_
from config import config


def app(doc):

    # Гистограмма пятна
    img = hist_storage_.get_hist()
    hist_source = ColumnDataSource(data=dict(image=[img]))
    scale_ = 6
    hist_fig = figure(plot_width=config.GEM_X * scale_, plot_height=config.GEM_Y * scale_,
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

    asym_fig = figure(plot_width=960, plot_height=400) # , x_range=[0, 10], y_range=[0, 10])
    asym_data_names = ['x_online', 'y_online', 'online_error_lower', 'online_error_upper', 'time', 'depol_freq']

    asym_source = ColumnDataSource({'x_online': [], 'y_online': [],
                                    'online_error_lower': [], 'online_error_upper': [],
                                    'time': [], 'depol_freq': []})

    # asym_fig.extra_x_ranges["depolarizer"] = FactorRange("c", 'f')
    asym_fig.extra_x_ranges["depolarizer"] = asym_fig.x_range  # Связал ось деполяризатора с осью времени

    asym_fig.add_layout(Whisker(source=asym_source, base="time",
                                upper="online_error_upper", lower="online_error_lower"))

    asym_fig.add_layout(LinearAxis(x_range_name="depolarizer"), 'below')

    asym_fig.circle('time', 'y_online', source=asym_source, size=8, color="black")

    asym_fig.yaxis[0].axis_label = "<y> [мм]"
    asym_fig.xaxis[0].axis_label = 'Время'
    asym_fig.xaxis[1].axis_label = 'Частота деполяризатора'
    # asym_fig.xaxis[1].major_label_overrides = {}


    asym_slider = Slider(start=1, end=10, value=1, step=1, title="Время усреднения")
    params = {'last_time': 0, 'period': 1}
    depol_dict = {}
    depol_list = []

    # 'x_start': 10**10, 'x_end': 0}

    # def asym_plot(points):

    def asym_update():

        if params['period'] != asym_slider.value:
            asym_source.data = {name: [] for name in asym_data_names}
            params['period'] = asym_slider.value
            params['last_time'] = 0

        points, params['last_time'] = data_storage_.get_mean_from(params['last_time'], params['period'])

        for i in range(len(points['time'])):
            depol_dict[int(points['time'][i])] = points['depol_freq'][i]
            depol_list.append(int(points['time'][i]))

        asym_source.stream(points, rollover=10000)
        asym_fig.xaxis[1].major_label_overrides = depol_dict
        asym_fig.xaxis[1].ticker = depol_list
        # doc.add_next_tick_callback(partial(asym_plot, points))

    # Окно статуса деполяризатора

    depol_status_window = Div(text="""Статус деполяризатора.
    Выключен""",
              width=200, height=100)

    depol_button = Button(label="Включить деполяризатор", button_type="success")

    # Инициализация bokeh app

    layout_ = layout([[hist_fig], [hist_slider], [asym_fig], [asym_slider], [depol_button, depol_status_window]])
    doc.add_root(layout_)
    doc.add_periodic_callback(hist_update, 1000)         # TODO запихнуть в один callback
    doc.add_periodic_callback(asym_update, 1000)         # TODO: подобрать периоды
    doc.title = "Laser polarimeter"


'''
def run_app(doc):


    layout = column(p)

    doc.add_root(layout)
    doc.add_periodic_callback(update, 1000)
    doc.title = "Selection Histogram"
    '''
