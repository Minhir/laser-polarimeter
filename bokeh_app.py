from bokeh.layouts import row, column, WidgetBox
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, Whisker, LinearAxis, HoverTool, BoxSelectTool, BoxAnnotation, Legend
from bokeh.models.callbacks import CustomJS
from bokeh.models.widgets import RangeSlider, Slider, Div, Button, TextInput, Panel, Tabs, RadioButtonGroup
from bokeh.models.widgets import Select, Paragraph, CheckboxGroup

import numpy as np
from math import pi
from data_storage import hist_storage_, data_storage_, names
from depolarizer import depolarizer
from config import config
import cpp.GEM as GEM
from fit import fit, get_line, create_fit_func


def app(doc):

    # вспомогательные глобальные

    fit_handler = {"fit_line": None, "input_fields": {}, "fit_indices": []}

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
        img = hist_storage_.get_hist(hist_buffer_len - hist_slider.value[1],
                                                             hist_buffer_len - hist_slider.value[0])
        # print(f"sum = {hist_storage_.get_events_num()}")
        hist_source.data = {'image': [img]}

    # График асимметрии

    asym_fig = figure(plot_width=width_, plot_height=height_ + 100,
                      tools="box_zoom, xbox_select, wheel_zoom, pan, save, reset, hover",
                      active_scroll="wheel_zoom", active_drag="pan", output_backend="webgl")

    def draw_selected_area(attr, old, new):
        if len(new.indices) <= 0:
            return
        fit_handler["fit_indices"] = sorted(new.indices)
        left_, right_ = fit_handler["fit_indices"][0], fit_handler["fit_indices"][-1]
        left_, right_ = asym_source.data['time'][left_], asym_source.data['time'][right_]
        BoxAnnotation(plot=asym_fig, left=left_, right=right_)

        asym_fig_box_select = (BoxAnnotation(left=left_,
                                             name="fit_zone",
                                             right=right_,
                                             fill_alpha=0.1, fill_color='red'))

        asym_fig.renderers = [r for r in asym_fig.renderers if r.name != 'fit_zone']  # TODO: fix не удаляет
        asym_fig.add_layout(asym_fig_box_select)

    asym_box_select_overlay = asym_fig.select_one(BoxSelectTool).overlay
    asym_box_select_overlay.line_color = "firebrick"

    asym_source = ColumnDataSource({key: [] for key in names})
    asym_source.on_change('selected', draw_selected_area)

    asym_fig.extra_x_ranges["depolarizer"] = asym_fig.x_range  # Связал ось деполяризатора с осью времени

    y_online_asym_error = Whisker(source=asym_source, base="time",
                                  upper="y_online_asym_up_error", lower="y_online_asym_down_error")

    y_cog_asym_error = Whisker(source=asym_source, base="time",
                               upper="y_cog_asym_up_error", lower="y_cog_asym_down_error")

    asym_fig.add_layout(y_online_asym_error)
    asym_fig.add_layout(y_cog_asym_error)
    asym_fig.add_layout(LinearAxis(x_range_name="depolarizer"), 'below')

    y_online_asym = asym_fig.circle('time', 'y_online_asym', source=asym_source, size=5, color="black",
                                    nonselection_alpha=1, nonselection_color="black")
    y_cog_asym = asym_fig.circle('time', 'y_cog_asym', source=asym_source, size=5, color="green",
                                 nonselection_alpha=1, nonselection_color="green")

    y_online_asym.js_on_change('visible', CustomJS(args=dict(x=y_online_asym_error),
                                                   code="x.visible = cb_obj.visible"))

    y_cog_asym.js_on_change('visible', CustomJS(args=dict(x=y_cog_asym_error),
                                                code="x.visible = cb_obj.visible"))

    legend = Legend(items=[
        ("ONE", [y_online_asym]),
        ("COG", [y_cog_asym]),
    ], location=(0, 0), click_policy="hide")

    asym_fig.add_layout(legend, 'below')

    asym_fig.yaxis[0].axis_label = "<Асимметрия по y [мм]"
    asym_fig.xaxis[0].axis_label = 'Время'
    asym_fig.xaxis[1].axis_label = 'Энергия деполяризатора'
    asym_fig.xaxis[1].major_label_orientation = pi / 2  # 0.52
    depol_list = []
    asym_fig.xaxis[1].major_label_overrides = {}

    hover = asym_fig.select(dict(type=HoverTool))
    hover.tooltips = [("Время", "@time"), ("Энергия деполяризации", "@depol_energy")]

    period_input = TextInput(value='300', title="Время усреднения (с):")
    params = {'last_time': 0, 'period': 1}

    def update_data():
        if params['period'] != int(period_input.value):
            asym_source.data = {name: [] for name in names}
            params['period'] = int(period_input.value)
            params['last_time'] = 0
            # asym_fig.xaxis[1].ticker.ticks.clear()
            depol_list.clear()

        points, params['last_time'] = data_storage_.get_mean_from(params['last_time'], params['period'])

        for i, time in enumerate(points['time']):
            if points['depol_energy'][i] == "0.000":
                continue
            asym_fig.xaxis[1].major_label_overrides[time] = points['depol_energy'][i]
            depol_list.append(time)

        asym_fig.xaxis[1].ticker = depol_list       # TODO: поменять
        asym_source.stream({key: np.array(val) for key, val in points.items()}, rollover=500)
        # doc.add_next_tick_callback(partial(asym_plot, points))

    def change_period(attr, old, new):
        if old == new:
            return

        try:
            val = int(new)
            if not (0 < val < 10000):
                raise ValueError("Некорректное значение")

        except ValueError as e:
            period_input.value = old
            print(e)

    period_input.on_change('value', change_period)

    # Настраиваемый график

    fig_names = [i + j for i in ["y_online", "y_cog"] for j in ['_l', '_r']] # TODO: создать держатель имен графиков
    fig_handler = []

    for fig_name in fig_names:
        fig = figure(plot_width=width_, plot_height=height_,
                     tools="box_zoom, wheel_zoom, pan, save, reset",
                     active_scroll="wheel_zoom", output_backend="webgl")

        fig.add_layout(Whisker(source=asym_source, base="time",
                               upper=fig_name + '_up_error',
                               lower=fig_name + '_down_error'))

        fig.circle('time', fig_name, source=asym_source, size=5, color="black",
                   nonselection_alpha=1, nonselection_color="black")
        fig.yaxis[0].axis_label = f"<{fig_name}> [мм]"
        fig.xaxis[0].axis_label = 'Время'
        fig.x_range = asym_fig.x_range
        fig_handler.append((fig, fig_name))

    for fig_name in ["rate", "corrected_rate"]:
        fig = figure(plot_width=width_, plot_height=height_,
                     tools="box_zoom, wheel_zoom, pan, save, reset",
                     active_scroll="wheel_zoom", output_backend="webgl")

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
        fig.x_range = asym_fig.x_range
        fig_handler.append((fig, fig_name))

    # Вкладки графика
    tab1 = Panel(child=asym_fig, title="Y")
    tabs = []
    for fig, fig_name in fig_handler:
        tabs.append(Panel(child=fig, title=fig_name))

    tab_handler = Tabs(tabs=tabs, width=width_)

    # Окно статуса деполяризатора

    # TODO: часы
    # TODO: временной офсет

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

    def update_depol_status():  # TODO: самому пересчитывать начало и конец
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

    fit_function_selection_widget = Select(title="Fitting function:", value="exp_jump",
                                           options=["exp_jump", "const"],
                                           width=200)

    fit_button = Button(label="FIT", width=200)

    def make_parameters_table(attr, old, new):
        line_name = fit_line_selection_widget.value
        name = fit_function_selection_widget.value

        t_width = 10
        t_height = 12
        delta_width = 0  # поправка на багу с шириной поля ввода
        m = create_fit_func(name,
                            asym_source.data['time'],
                            asym_source.data[line_name],
                            [i - j for i, j in zip(asym_source.data[line_name + '_up_error'],
                            asym_source.data[line_name])],
                            {})

        rows = [row(Paragraph(text="name", width=t_width, height=t_height),
                    Paragraph(text="Fix", width=t_width, height=t_height),
                    Paragraph(text="Init value", width=t_width + delta_width, height=t_height),
                    Paragraph(text="step (error)", width=t_width + delta_width, height=t_height),
                    Paragraph(text="bounds", width=t_width, height=t_height),
                    Paragraph(text="start", width=t_width + delta_width, height=t_height),
                    Paragraph(text="stop", width=t_width + delta_width, height=t_height))]

        fit_handler["input_fields"] = {}

        for param in m.parameters:
            fit_handler["input_fields"][param] = {}
            fit_handler["input_fields"][param]["fix"] = CheckboxGroup(labels=[""], width=t_width, height=t_height)
            fit_handler["input_fields"][param]["Init value"] = TextInput(width=t_width + delta_width, height=t_height, value="1")
            fit_handler["input_fields"][param]["step (error)"] = TextInput(width=t_width + delta_width, height=t_height)
            fit_handler["input_fields"][param]["bounds"] = CheckboxGroup(labels=[""], width=t_width, height=t_height)
            fit_handler["input_fields"][param]["start"] = TextInput(width=t_width + delta_width, height=t_height)
            fit_handler["input_fields"][param]["stop"] = TextInput(width=t_width + delta_width, height=t_height)

            rows.append(row(Paragraph(text=param, width=t_width, height=t_height),
                            fit_handler["input_fields"][param]["fix"],
                            fit_handler["input_fields"][param]["Init value"],
                            fit_handler["input_fields"][param]["step (error)"],
                            fit_handler["input_fields"][param]["bounds"],
                            fit_handler["input_fields"][param]["start"],
                            fit_handler["input_fields"][param]["stop"]))

        return column(rows)

    def clear_fit():
        if fit_handler["fit_line"] in asym_fig.renderers:
            asym_fig.renderers.remove(fit_handler["fit_line"])

    energy_window = Div(text="Частота: , энергия: ")
    clear_fit_button = Button(label="Clear", width=200)
    clear_fit_button.on_click(clear_fit)

    def fit_callback():
        if fit_handler["fit_line"] in asym_fig.renderers:
            asym_fig.renderers.remove(fit_handler["fit_line"])

        name = fit_function_selection_widget.value
        line_name = fit_line_selection_widget.value
        fit_indices = fit_handler["fit_indices"]
        if fit_indices:
            x_axis = [asym_source.data['time'][i] for i in fit_indices]
            y_axis = [asym_source.data[line_name][i] for i in fit_indices]
            y_errors = [asym_source.data[line_name + '_up_error'][i] - asym_source.data[line_name][i] for i in fit_indices]
        else:
            x_axis = asym_source.data['time']
            y_axis = asym_source.data[line_name]
            y_errors = [i - j for i, j in zip(asym_source.data[line_name + '_up_error'], asym_source.data[line_name])]
        m = create_fit_func(name,
                            x_axis,
                            y_axis,
                            y_errors,
                            {name: float(fit_handler["input_fields"][name]["Init value"].value) for name in fit_handler["input_fields"].keys()})

        fit(m)  # TODO: в отдельный поток?
        params_ = m.get_param_states()
        for i in params_:
            fit_handler["input_fields"][i['name']]["Init value"].value = str(i['value'])
            if i['name'] == "depol_time":
                freq = depolarizer.find_closest_freq(i['value'] + data_storage_.start_time)
                energy = depolarizer.frequency_to_energy(freq) if freq != 0 else 0
                energy_window.text = f"<p>Частота: {freq}, энергия: {energy}</p>"

        fit_handler["fit_line"] = asym_fig.line(x_axis,  # TODO: менять кол-во точек
                                                get_line(name, asym_source.data['time'], [x['value'] for x in params_]),
                                                color="red", line_width=2)

    fit_button.on_click(fit_callback)

     # {depol_time = 50, P0 = 0, Pmax = 10, tau = 14, DELTA = 0, T = 1}

    # Инициализация bokeh app
    column_1 = column(tab_handler, asym_fig, period_input, width=width_ + 50)
    widgets_ = WidgetBox(depol_start_stop_buttons, fake_depol_button,
                         depol_input_harmonic_number, depol_input_attenuation, depol_input_speed,
                         depol_input_step, depol_input_initial,
                         depol_input_final, depol_status_window)

    row_21 = column(hist_fig, hist_slider)
    column_21 = column(widgets_)
    column_22 = column(fit_button, clear_fit_button, fit_line_selection_widget, fit_function_selection_widget,
                       energy_window, make_parameters_table(None, None, None))

    def rebuild_table(attr, old, new):
        column_22.children[5] = make_parameters_table(None, None, None)

    fit_function_selection_widget.on_change("value", rebuild_table)

    row_22 = row(column_21, column_22)
    column_2 = column(row_21, row_22, width=width_ + 50)
    layout_ = row(column_1, column_2)

    def pr_har():
        print(depolarizer.get_by_name("harmonic_number"))

    doc.add_root(layout_)
    doc.add_periodic_callback(hist_update, 1000)         # TODO запихнуть в один callback
    doc.add_periodic_callback(update_data, 1000)         # TODO: подобрать периоды
    doc.add_periodic_callback(update_depol_status, 1000)
    doc.title = "Laser polarimeter"
