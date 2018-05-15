import bisect
from math import pi

from bokeh.layouts import row, column, WidgetBox
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, Whisker, LinearAxis, HoverTool, BoxSelectTool, BoxAnnotation, Legend, Label
from bokeh.models.callbacks import CustomJS
from bokeh.models.widgets import RangeSlider, Div, Button, TextInput, Panel, Tabs, RadioButtonGroup
from bokeh.models.widgets import Select, Paragraph, CheckboxGroup
from bokeh.models.formatters import DatetimeTickFormatter
import numpy as np

from data_storage import hist_storage_, data_storage_, names, freq_storage_
from depolarizer import depolarizer
from config import config
import cpp.GEM as GEM
import fit


def app(doc):

    # вспомогательные глобальные

    fit_handler = {"fit_line": None, "input_fields": {}, "fit_indices": tuple()}
    data_names = names
    utc_plus_7h = 7 * 3600

    datetime_formatter = DatetimeTickFormatter(
        milliseconds=['%M:%S:%3Nms'],
        seconds=['%H:%M:%S'],
        minsec=['%H:%M:%S'],
        minutes=['%H:%M:%S'],
        hourmin=['%H:%M:%S'],
        hours=['%H:%M:%S'],
        days=["%d.%m"],
        months=["%Y-%m-%d"],
    )

    # Гистограмма пятна
    img, img_x_std, img_y_std = hist_storage_.get_hist_with_std()
    hist_source = ColumnDataSource(data=dict(image=[img]))
    width_ = config.GEM_X * 5
    hist_height_ = config.GEM_Y * 5
    height_ = 300
    hist_fig = figure(plot_width=width_, plot_height=hist_height_,
                      x_range=(0, config.GEM_X), y_range=(0, config.GEM_Y))

    hist_fig.image(image='image', x=0, y=0, dw=config.GEM_X, dh=config.GEM_Y, palette="Spectral11", source=hist_source)

    hist_label = Label(x=0, y=0, x_units='screen', y_units='screen',
                       text=f"x_std={'%.2f' % img_x_std},y_std={'%.2f' % img_y_std}", render_mode='css',
                       border_line_color='black', border_line_alpha=1.0,
                       background_fill_color='white', background_fill_alpha=1.0)

    hist_fig.add_layout(hist_label)

    hist_buffer_len = config.hist_buffer_len - 1
    hist_slider = RangeSlider(start=0, end=hist_buffer_len, value=(0, hist_buffer_len),
                              step=1, title="Срез пятна (от..до) сек назад")

    def hist_update():
        img, img_x_std, img_y_std = hist_storage_.get_hist_with_std(hist_buffer_len - hist_slider.value[1],
                                                                    hist_buffer_len - hist_slider.value[0])
        hist_label.text = f"x_std={'%.2f' % img_x_std},y_std={'%.2f' % img_y_std}"
        hist_source.data = {'image': [img]}

    # График асимметрии

    asym_fig = figure(plot_width=width_, plot_height=height_ + 100,
                      tools="box_zoom, xbox_select, wheel_zoom, pan, save, reset",
                      active_scroll="wheel_zoom", active_drag="pan",
                      lod_threshold=100, x_axis_type="datetime", toolbar_location="below")

    def draw_selected_area(attr, old, new):
        """Подсветка выделенной для подгонки области"""
        if not new.indices:
            return

        left_time_, right_time_ = asym_source.data['time'][min(new.indices)], asym_source.data['time'][max(new.indices)]
        fit_handler["fit_indices"] = (left_time_, right_time_)
        asym_fig_box_select = BoxAnnotation(left=left_time_,
                                            name="fit_zone",
                                            right=right_time_,
                                            fill_alpha=0.1, fill_color='red')

        asym_fig.renderers = [r for r in asym_fig.renderers if r.name != 'fit_zone']
        asym_fig.add_layout(asym_fig_box_select)

    asym_box_select_overlay = asym_fig.select_one(BoxSelectTool).overlay
    asym_box_select_overlay.line_color = "firebrick"

    asym_source = ColumnDataSource({key: [] for key in data_names})
    asym_source.on_change('selected', draw_selected_area)

    asym_fig.extra_x_ranges["depolarizer"] = asym_fig.x_range  # Связал ось деполяризатора с осью времени

    y_online_asym_error = Whisker(source=asym_source, base="time",
                                  upper="y_online_asym_up_error", lower="y_online_asym_down_error")

    y_cog_asym_error = Whisker(source=asym_source, base="time",
                               upper="y_cog_asym_up_error", lower="y_cog_asym_down_error")

    asym_fig.add_layout(y_online_asym_error)
    asym_fig.add_layout(y_cog_asym_error)
    asym_fig.add_layout(LinearAxis(x_range_name="depolarizer"), 'below')

    online_asym_renderer = asym_fig.circle('time', 'y_online_asym', source=asym_source, size=5, color="black",
                                           nonselection_alpha=1, nonselection_color="black")
    cog_asym_renderer = asym_fig.circle('time', 'y_cog_asym', source=asym_source, size=5, color="green",
                                        nonselection_alpha=1, nonselection_color="green")

    online_asym_renderer.js_on_change('visible', CustomJS(args=dict(x=y_online_asym_error),
                                                          code="x.visible = cb_obj.visible"))

    cog_asym_renderer.js_on_change('visible', CustomJS(args=dict(x=y_cog_asym_error),
                                                       code="x.visible = cb_obj.visible"))

    legend = Legend(
        items=[("ONE", [online_asym_renderer]),
               ("COG", [cog_asym_renderer])],
        location=(0, 0), click_policy="hide")

    asym_fig.add_layout(legend, 'below')

    asym_fig.yaxis[0].axis_label = '<Асимметрия по y [мм]'
    asym_fig.xaxis[0].axis_label = 'Время'
    asym_fig.xaxis[1].axis_label = 'Деполяризатор'
    asym_fig.xaxis[1].major_label_orientation = pi / 2
    asym_fig.xaxis[1].major_label_overrides = {}
    asym_fig.xaxis[0].formatter = datetime_formatter

    # Вывод информации по точке при наведении мыши

    asym_fig.add_tools(HoverTool(
        renderers=[online_asym_renderer],
        formatters={"time": "datetime"},
        tooltips=[("Тип", "ONE"), ("Время", "@time{%F %T}"),
                  ("Деполяризатор", "@depol_energy"), ("y", "@y_online_asym")]))

    asym_fig.add_tools(HoverTool(
        renderers=[cog_asym_renderer],
        formatters={"time": "datetime"},
        tooltips=[("Тип", "COG"), ("Время", "@time{%F %T}"),
                  ("Деполяризатор", "@depol_energy"), ("y", "@y_cog_asym")]))

    # Окно ввода периода усреднения
    period_input = TextInput(value='300', title="Время усреднения (с):")

    # Глобальный список параметров, для сохранения результатов запросов к data_storage
    params = {'last_time': 0, 'period': int(period_input.value)}

    depol_list = []

    def update_data():
        """
        Обновляет данные для пользовательского интерфейса, собирая их у data_storage
        """
        if params['period'] != int(period_input.value):
            asym_source.data = {name: [] for name in data_names}
            params['period'] = int(period_input.value)
            params['last_time'] = 0
            # asym_fig.xaxis[1].ticker.ticks.clear()
            depol_list.clear()

        points, params['last_time'] = data_storage_.get_mean_from(params['last_time'], params['period'])

        points['time'] = [(i + utc_plus_7h) * 10**3 for i in points['time']]  # Учёт сдвижки UTC+7 для отрисовки

        for i, time in enumerate(points['time']):
            if points['depol_energy'][i] == "0.000":
                continue
            asym_fig.xaxis[1].major_label_overrides[time] = points['depol_energy'][i]
            depol_list.append(time)

        asym_fig.xaxis[1].ticker = depol_list       # TODO: поменять

        asym_source.stream({key: np.array(val) for key, val in points.items()}, rollover=250)

    def change_period(attr, old, new):
        if old == new:
            return
        try:
            val = int(new)
            if not (0 < val < config.asym_buffer_len):
                raise ValueError("Некорректное значение")

        except ValueError as e:
            period_input.value = old
            print(e)

    period_input.on_change('value', change_period)

    # Настраиваемый график

    fig_names = [i + j for i in ["y_online", "y_cog"] for j in ['_l', '_r']]  # TODO: создать держатель имен графиков
    fig_handler = []

    for fig_name in fig_names:
        fig = figure(plot_width=width_, plot_height=height_,
                     tools="box_zoom, wheel_zoom, pan, save, reset",
                     active_scroll="wheel_zoom", lod_threshold=100, x_axis_type="datetime")

        fig.add_layout(Whisker(source=asym_source, base="time",
                               upper=fig_name + '_up_error',
                               lower=fig_name + '_down_error'))

        fig.circle('time', fig_name, source=asym_source, size=5, color="black",
                   nonselection_alpha=1, nonselection_color="black")
        fig.yaxis[0].axis_label = f"<{fig_name}> [мм]"
        fig.xaxis[0].axis_label = 'Время'
        fig.xaxis[0].formatter = datetime_formatter
        fig.x_range = asym_fig.x_range
        fig_handler.append((fig, fig_name))

    for fig_name in ["rate", "corrected_rate"]:
        fig = figure(plot_width=width_, plot_height=height_,
                     tools="box_zoom, wheel_zoom, pan, save, reset",
                     active_scroll="wheel_zoom", lod_threshold=100, x_axis_type="datetime")

        fig_name_l = fig_name + "_l"
        fig_name_r = fig_name + "_r"
        fig.add_layout(Whisker(source=asym_source, base="time",
                               upper=fig_name_l + '_up_error',
                               lower=fig_name_l + '_down_error', line_color='blue',
                               lower_head=None, upper_head=None))

        fig.add_layout(Whisker(source=asym_source, base="time",
                       upper=fig_name_r + '_up_error',
                       lower=fig_name_r + '_down_error', line_color='red',
                       lower_head=None, upper_head=None))

        fig.circle('time', fig_name_l, source=asym_source, size=5, color="blue",
                   nonselection_alpha=1, nonselection_color="blue")

        fig.circle('time', fig_name_r, source=asym_source, size=5, color="red",
                   nonselection_alpha=1, nonselection_color="red")

        fig.yaxis[0].axis_label = f"<{fig_name}>"
        fig.xaxis[0].axis_label = 'Время'
        fig.xaxis[0].formatter = datetime_formatter
        fig.x_range = asym_fig.x_range
        fig_handler.append((fig, fig_name))

    fig = figure(plot_width=width_, plot_height=height_,
                 tools="box_zoom, wheel_zoom, pan, save, reset",
                 active_scroll="wheel_zoom", lod_threshold=100, x_axis_type="datetime")

    fig.circle('time', "charge", source=asym_source, size=5, color="blue",
               nonselection_alpha=1, nonselection_color="blue")

    fig.yaxis[0].axis_label = "Заряд"
    fig.xaxis[0].axis_label = 'Время'
    fig.xaxis[0].formatter = datetime_formatter
    fig.x_range = asym_fig.x_range

    fig_handler.append((fig, 'charge'))

    # Вкладки графика
    tab_handler = Tabs(tabs=[Panel(child=fig, title=fig_name) for fig, fig_name in fig_handler], width=width_)

    # Окно статуса деполяризатора

    depol_status_window = Div(text="Инициализация...", width=500, height=500)

    depol_start_stop_buttons = RadioButtonGroup(labels=["Старт", "Стоп"],
                                                active=(0 if depolarizer.is_scan else 1))

    fake_depol_button = Button(label="Деполяризовать", width=200)
    fake_depol_button.on_click(GEM.depolarize)

    depol_input_harmonic_number = TextInput(value=str('%.1f' % depolarizer.harmonic_number),
                                            title=f"Номер гармоники", width=150)

    depol_input_attenuation = TextInput(value=str('%.1f' % depolarizer.attenuation),
                                        title=f"Аттенюатор (дБ)", width=150)

    depol_input_speed = TextInput(value=str(depolarizer.frequency_to_energy(depolarizer.speed, n=0)),
                                  title=f"Скорость ({'%.1f' % depolarizer.speed} Гц):", width=150)

    depol_input_step = TextInput(value=str(depolarizer.frequency_to_energy(depolarizer.step, n=0)),
                                 title=f"Шаг ({'%.1f' % depolarizer.step} Гц):", width=150)

    depol_input_initial = TextInput(value=str(depolarizer.frequency_to_energy(depolarizer.initial)),
                                    title=f"Начало ({'%.1f' % depolarizer.initial} Гц):", width=150)

    depol_input_final = TextInput(value=str(depolarizer.frequency_to_energy(depolarizer.final)),
                                  title=f"Конец ({'%.1f' % depolarizer.final} Гц):", width=150)

    depol_dict = {"speed": (depol_input_speed, depolarizer.set_speed),
                  "step": (depol_input_step, depolarizer.set_step),
                  "initial": (depol_input_initial, depolarizer.set_initial),
                  "final": (depol_input_final, depolarizer.set_final),
                  "harmonic_number": (depol_input_harmonic_number, depolarizer.set_harmonic_number),
                  "attenuation": (depol_input_attenuation, depolarizer.set_attenuation)}

    def change_value_generator(value_name):
        """Возвращает callback функцию для параметра value_name деполяризатора"""
        def change_value(attr, old, new):
            if float(old) == float(new):
                return

            depol_input, depol_set = depol_dict[value_name]
            depol_current = depolarizer.get_by_name(value_name)
            try:
                if value_name in ['harmonic_number', 'attenuation']:
                    new_val = float(new)
                elif value_name in ['speed', 'step']:
                    new_val = depolarizer.energy_to_frequency(float(new), n=0)
                else:
                    new_val = depolarizer.energy_to_frequency(float(new))

                if depol_current == new_val:
                    return

                depol_set(new_val)
                if value_name not in ['harmonic_number', 'attenuation']:
                    name = depol_input.title.split(' ')[0]
                    depol_input.title = name + f" ({'%.1f' % new_val} Гц):"

            except ValueError as e:
                if value_name in ['harmonic_number', 'attenuation']:
                    depol_input.value = str(depol_current)
                elif value_name in ['speed', 'step']:
                    depol_input.value = str(depolarizer.frequency_to_energy(depol_current, n=0))
                else:
                    depol_input.value = str(depolarizer.frequency_to_energy(depol_current))
                print(e)

        return change_value

    depol_input_harmonic_number.on_change('value', change_value_generator('harmonic_number'))
    depol_input_attenuation.on_change('value', change_value_generator("attenuation"))
    depol_input_speed.on_change('value', change_value_generator("speed"))
    depol_input_step.on_change('value', change_value_generator("step"))
    depol_input_initial.on_change('value', change_value_generator("initial"))
    depol_input_final.on_change('value', change_value_generator("final"))

    def update_depol_status():  # TODO: самому пересчитывать начало и конец сканирования по частотам
        """Обновляет статус деполяризатора,
        если какое-то значение поменялось другим пользователем"""
        depol_start_stop_buttons.active = (0 if depolarizer.is_scan else 1)

        depol_status_window.text = f"""
<p>Сканирование: 
<font color={'"green">включено' if depolarizer.is_scan else '"red">выключено'}</font></p>
<p/>Частота {"%.1f" % depolarizer.current_frequency} (Гц)</p>"""

        for value_name in ['speed', 'step']:
            depol_input, _ = depol_dict[value_name]
            depol_value = depolarizer.frequency_to_energy(depolarizer.get_by_name(value_name), n=0)
            if float(depol_input.value) != depol_value:
                depol_input.value = str(depol_value)

        for value_name in ['initial', 'final']:
            depol_input, _ = depol_dict[value_name]
            freq = depolarizer.get_by_name(value_name)
            energy = depolarizer.frequency_to_energy(freq)
            if float(depol_input.value) != energy:
                depol_input.value = str(energy)
            else:
                name = depol_input.title.split(' ')[0]
                depol_input.title = name + f" ({'%.1f' % freq} Гц):"

        for value_name in ['attenuation', 'harmonic_number']:
            depol_input, _ = depol_dict[value_name]
            depol_value = depolarizer.get_by_name(value_name)
            if float(depol_input.value) != depol_value:
                depol_input.value = str(int(depol_value))

    depol_start_stop_buttons.on_change("active",
                                       lambda attr, old, new: (depolarizer.start_scan() if new == 0 else depolarizer.stop_scan()))

    # Подгонка

    fit_line_selection_widget = Select(title="Fitting line:", value="y_online_asym",
                                       options=["y_online_asym", "y_cog_asym"],
                                       width=200)

    options = [name for name in fit.function_handler.keys()]
    if not options:
        raise IndexError("Пустой function_handler в fit.py")

    fit_function_selection_widget = Select(title="Fitting function:", value=options[0],
                                           options=options, width=200)

    fit_button = Button(label="FIT", width=200)

    def make_parameters_table(attr, old, new):      # TODO: перенести на JavaScript
        """Создание поля ввода данных для подгонки: начальное значение, fix и т.д."""
        name = fit_function_selection_widget.value

        t_width = 10
        t_height = 12

        rows = [row(Paragraph(text="name", width=t_width, height=t_height),
                    Paragraph(text="Fix", width=t_width, height=t_height),
                    Paragraph(text="Init value", width=t_width, height=t_height),
                    Paragraph(text="step (error)", width=t_width, height=t_height),
                    Paragraph(text="limits", width=t_width, height=t_height),
                    Paragraph(text="lower_limit", width=t_width, height=t_height),
                    Paragraph(text="upper_limit", width=t_width, height=t_height))]

        fit_handler["input_fields"] = {}

        for param, value in fit.get_function_params(name):
            fit_handler["input_fields"][param] = {}
            fit_handler["input_fields"][param]["fix"] = CheckboxGroup(labels=[""], width=t_width, height=t_height)
            fit_handler["input_fields"][param]["Init value"] = TextInput(width=t_width,
                                                                         height=t_height, value=str(value))
            fit_handler["input_fields"][param]["step (error)"] = TextInput(width=t_width, height=t_height)
            fit_handler["input_fields"][param]["limits"] = CheckboxGroup(labels=[""], width=t_width, height=t_height)
            fit_handler["input_fields"][param]["lower_limit"] = TextInput(width=t_width, height=t_height)
            fit_handler["input_fields"][param]["upper_limit"] = TextInput(width=t_width, height=t_height)

            rows.append(row(Paragraph(text=param, width=t_width, height=t_height),
                            fit_handler["input_fields"][param]["fix"],
                            fit_handler["input_fields"][param]["Init value"],
                            fit_handler["input_fields"][param]["step (error)"],
                            fit_handler["input_fields"][param]["limits"],
                            fit_handler["input_fields"][param]["lower_limit"],
                            fit_handler["input_fields"][param]["upper_limit"]))

        return column(rows)

    def clear_fit():
        """Удаление подогнанной кривой"""
        if fit_handler["fit_line"] in asym_fig.renderers:
            asym_fig.renderers.remove(fit_handler["fit_line"])

    energy_window = Div(text="Частота: , энергия: ")
    clear_fit_button = Button(label="Clear", width=200)
    clear_fit_button.on_click(clear_fit)

    def fit_callback():
        clear_fit()

        name = fit_function_selection_widget.value
        line_name = fit_line_selection_widget.value

        if fit_handler["fit_indices"]:
            left_time_, right_time_ = fit_handler["fit_indices"]

            left_ind_ = bisect.bisect_left(asym_source.data['time'], left_time_)
            right_ind_ = bisect.bisect_right(asym_source.data['time'], right_time_, lo=left_ind_)

            x_axis = asym_source.data['time'][left_ind_:right_ind_]
            y_axis = asym_source.data[line_name][left_ind_:right_ind_]
            y_errors = asym_source.data[line_name + '_up_error'][left_ind_:right_ind_] - asym_source.data[line_name][left_ind_:right_ind_]
        else:
            x_axis = asym_source.data['time']
            y_axis = asym_source.data[line_name]
            y_errors = asym_source.data[line_name + '_up_error'] - asym_source.data[line_name]

        if len(x_axis) == 0:
            return

        init_vals = {name: float(fit_handler["input_fields"][name]["Init value"].value)
                     for name in fit_handler["input_fields"].keys()}

        fix_vals = {"fix_" + name: True for name in fit_handler["input_fields"].keys()
                    if fit_handler["input_fields"][name]["fix"].active}

        limit_vals = {"limit_" + name: (float(fit_handler["input_fields"][name]["lower_limit"].value),
                                        float(fit_handler["input_fields"][name]["upper_limit"].value))
                      for name in fit_handler["input_fields"].keys()
                      if fit_handler["input_fields"][name]["limits"].active}

        kwargs = {}
        kwargs.update(init_vals)
        kwargs.update(fix_vals)
        kwargs.update(limit_vals)

        # Предобработка времени, перевод в секунды, вычитание сдвига (для лучшей подгонки)
        x_time = x_axis / 10**3  # Перевёл в секунды        TODO: вычиать левую границу графику
        x_min = x_time[0]
        x_time -= x_min  # Привёл время в интервал от 0
        x_max = x_time[-1]

        # Создание точек, которые передадутся в подогнанную функцию с параметрами,
        # и точек, которые соответсвуют реальным временам на графике (т.е. без смещения к 0)

        points_amount = 300
        fit_line_real_x_axis = np.linspace(x_axis[0], x_axis[-1], points_amount)
        fit_line_x_axis = np.linspace(0, x_max, points_amount)

        m = fit.create_fit_func(name, x_time, y_axis, y_errors, kwargs)

        fit.fit(m)  # TODO: в отдельный поток?
        params_ = m.get_param_states()
        for param in params_:
            fit_handler["input_fields"][param['name']]["Init value"].value = str(param['value'])
            if param['name'] == "depol_time":
                freq = freq_storage_.find_closest_freq(param['value'] + x_min)
                energy = depolarizer.frequency_to_energy(freq) if freq != 0 else 0
                energy_window.text = f"<p>Частота: {freq}, энергия: {energy}</p>"

        fit_handler["fit_line"] = asym_fig.line(fit_line_real_x_axis,
                                                fit.get_line(name, fit_line_x_axis, [x['value'] for x in params_]),
                                                color="red", line_width=2)

    fit_button.on_click(fit_callback)

    # Инициализация bokeh app, расположение виджетов
    column_1 = column(tab_handler, asym_fig, period_input, width=width_ + 50)
    widgets_ = WidgetBox(depol_start_stop_buttons,
                         depol_input_harmonic_number, depol_input_attenuation, depol_input_speed,
                         depol_input_step, depol_input_initial,
                         depol_input_final, depol_status_window)

    row_21 = column(hist_fig, hist_slider)
    column_21 = column(widgets_)
    if config.GEM_idle:
        column_22 = column(fit_button, clear_fit_button, fake_depol_button, fit_line_selection_widget,
                           fit_function_selection_widget, energy_window, make_parameters_table(None, None, None))
        make_parameters_table_id = 6
    else:
        column_22 = column(fit_button, clear_fit_button, fit_line_selection_widget,
                           fit_function_selection_widget, energy_window, make_parameters_table(None, None, None))
        make_parameters_table_id = 5

    def rebuild_table(attr, old, new):
        column_22.children[make_parameters_table_id] = make_parameters_table(None, None, None)

    fit_function_selection_widget.on_change("value", rebuild_table)

    row_22 = row(column_21, column_22)
    column_2 = column(row_21, row_22, width=width_ + 50)
    layout_ = row(column_1, column_2)

    # update_data()
    doc.add_root(layout_)
    doc.add_periodic_callback(hist_update, 1000)         # TODO запихнуть в один callback
    doc.add_periodic_callback(update_data, 1000)         # TODO: подобрать периоды
    doc.add_periodic_callback(update_depol_status, 1000)
    doc.title = "Laser polarimeter"
