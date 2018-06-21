import bisect
from math import pi

from bokeh.layouts import row, column, WidgetBox, gridplot, layout
from bokeh.plotting import figure
from bokeh.models import (ColumnDataSource, Whisker, LinearAxis, HoverTool, BoxSelectTool, BoxAnnotation, Legend,
                          Label, DataRange1d, Span)
from bokeh.models.callbacks import CustomJS
from bokeh.events import DoubleTap
from bokeh.models.widgets import RangeSlider, Div, Button, TextInput, Panel, Tabs, RadioButtonGroup
from bokeh.models.widgets import Select, Paragraph, CheckboxGroup
from bokeh.models.formatters import DatetimeTickFormatter, FuncTickFormatter
import numpy as np

from config import config
import cpp.GEM as GEM
import fit


def app(doc, hist_storage_, data_storage_, freq_storage_, depolarizer, names):

    # вспомогательные глобальные

    data_source = ColumnDataSource({key: [] for key in names})
    fit_handler = {"fit_line": None, "input_fields": {}, "fit_indices": tuple()}
    utc_plus_7h = 7 * 3600
    time_coef = 10**3  # Пересчёт времени в мс для формата datetime Bokeh
    fit_line_points_amount = 300
    depol_list = []

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

    asym_fig = figure(plot_width=width_, plot_height=400,
                      tools="box_zoom, xbox_select, wheel_zoom, pan, save, reset",
                      active_scroll="wheel_zoom", active_drag="pan", toolbar_location="below",
                      lod_threshold=100, x_axis_location=None, x_range=DataRange1d())

    asym_fig.yaxis.axis_label = "мм"
    asym_fig.extra_x_ranges = {"time_range": asym_fig.x_range,
                               "depolarizer": asym_fig.x_range,
                               "sec": asym_fig.x_range}

    depol_axis = LinearAxis(x_range_name="depolarizer", axis_label='Деполяризатор',
                            major_label_overrides={}, major_label_orientation=pi/2)

    asym_fig.add_layout(LinearAxis(x_range_name="time_range", axis_label='Время',
                                   formatter=datetime_formatter), 'below')

    zone_of_interest = Span(location=0,
                            dimension='height', line_color='green',
                            line_dash='dashed', line_width=3)

    sec_axis = LinearAxis(x_range_name='sec', axis_label='Секунды')  # Секундная ось сверху (настр. диапазон)
    sec_axis.formatter = FuncTickFormatter(
        code=f"return ((tick - {zone_of_interest.location}) / {time_coef}).toFixed(1);")

    def double_tap(event):
        zone_of_interest.location = event.x
        sec_axis.formatter = FuncTickFormatter(code=f"return ((tick - {event.x}) / {time_coef}).toFixed(1);")

    asym_fig.add_layout(depol_axis, 'below')
    asym_fig.add_layout(sec_axis, 'above')
    asym_fig.add_layout(zone_of_interest)
    asym_fig.on_event(DoubleTap, double_tap)

    def draw_selected_area(attr, old, new):
        """Подсветка выделенной для подгонки области"""

        # Удаляет предыдущую выделенную область
        asym_fig.renderers = [r for r in asym_fig.renderers if r.name != 'fit_zone']
        fit_handler["fit_indices"] = tuple()

        if new.indices:
            left_time_ = data_source.data['time'][min(new.indices)]
            right_time_ = data_source.data['time'][max(new.indices)]

            if left_time_ != right_time_:
                fit_handler["fit_indices"] = (left_time_, right_time_)

        asym_fig_box_select = BoxAnnotation(left=left_time_,
                                            name="fit_zone",
                                            right=right_time_,
                                            fill_alpha=0.1, fill_color='red')

        asym_fig.add_layout(asym_fig_box_select)

    asym_box_select_overlay = asym_fig.select_one(BoxSelectTool).overlay
    asym_box_select_overlay.line_color = "firebrick"

    data_source.on_change('selected', draw_selected_area)

    def create_whisker(data_name: str):
        """ Создает усы для data_name от time

        :param data_name: имя поля данных из data_storage
                (у данных должны быть поля '_up_error', '_down_error')
        :return: Bokeh Whisker
        """
        return Whisker(source=data_source, base="time", upper=data_name+"_up_error", lower=data_name+"_down_error")

    def create_render(data_name: str, glyph: str, color: str):
        """ Рисует data_name от time

        :param data_name: имя поля данных из data_storage
        :param glyph: ['circle', 'square']
        :param color: цвет
        :return: Bokeh fig
        """
        if glyph == 'circle':
            func = asym_fig.circle
        elif glyph == 'square':
            func = asym_fig.square
        else:
            raise ValueError('Неверное значение glyph')
        return func('time', data_name, source=data_source, name=data_name, color=color,
                    nonselection_alpha=1, nonselection_color=color)

    # Список линий на графике асимметрии: data_name, name, glyph, color
    asym_renders_name = [('y_one_asym', 'ΔY ONE', 'circle', 'black'),
                         ('y_cog_asym', 'ΔY COG', 'circle', 'green'),
                         ('x_one_asym', 'ΔX ONE', 'square', 'black'),
                         ('x_cog_asym', 'ΔX COG', 'square', 'green')]

    pretty_names = dict([(data_name, name) for data_name, name, *_ in asym_renders_name])
    asym_renders = [create_render(data_name, glyph, color) for data_name, _, glyph, color in asym_renders_name]
    asym_error_renders = [create_whisker(data_name) for data_name, *_ in asym_renders_name]

    for render, render_error in zip(asym_renders, asym_error_renders):
        asym_fig.add_layout(render_error)
        render.js_on_change('visible', CustomJS(args=dict(x=render_error), code="x.visible = cb_obj.visible"))

    asym_fig.add_layout(Legend(items=[(pretty_names[r.name], [r]) for r in asym_renders], click_policy="hide",
                               location="top_left", background_fill_alpha=0.2, orientation="horizontal"))

    # Вывод информации по точке при наведении мыши

    asym_fig.add_tools(HoverTool(
        renderers=asym_renders,
        formatters={"time": "datetime"},
        mode='vline',
        tooltips=[("Время", "@time{%F %T}"),
                  *[(pretty_names[r.name], f"@{r.name}{'{0.000}'} ± @{r.name + '_error'}{'{0.000}'}")
                    for r in asym_renders],
                  ("Деполяризатор", f"@depol_energy{'{0.000}'}")]))

    # Окно ввода периода усреднения
    period_input = TextInput(value='300', title="Время усреднения (с):")

    # Глобальный список параметров, для сохранения результатов запросов к data_storage
    params = {'last_time': 0, 'period': int(period_input.value)}

    def update_data():
        """
        Обновляет данные для пользовательского интерфейса, собирая их у data_storage
        """
        if params['period'] != int(period_input.value):
            data_source.data = {name: [] for name in names}
            params['period'] = int(period_input.value)
            params['last_time'] = 0
            depol_axis.ticker = []
            depol_axis.major_label_overrides.clear()
            depol_list.clear()

        points, params['last_time'] = data_storage_.get_mean_from(params['last_time'], params['period'])

        if not points['time']:
            return

        points['time'] = [(i + utc_plus_7h) * time_coef for i in points['time']]  # Учёт сдвижки UTC+7 для отрисовки

        for time, energy in zip(points['time'], points['depol_energy']):
            if energy == 0:
                continue
            depol_axis.major_label_overrides[time] = str(energy)
            depol_list.append(time)

        depol_axis.ticker = depol_list      # TODO: оптимизировать
        data_source.stream({key: np.array(val) for key, val in points.items()}, rollover=250)

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

    # Создание панели графиков (вкладок)

    def create_fig(data_names: list, colors: list, y_axis_name: str, ers: str=None):
        """Создаёт график data_names : time. Если в data_names несколько имён,
        то они будут на одном графике. Возвращает fig.

        :param data_names: список с именами полей данных из data_storage
        :param colors: список цветов, соотв. элементам из fig_names
        :param y_axis_name: имя оси Y
        :param ers: 'err', 'pretty' --- вид усов (у данных должны быть поля '_up_error', '_down_error'),
                       'err' --- усы обыкновенные
                       'pretty' --- усы без шляпки и цветом совпадающим с цветом точки
        :return fig --- Bokeh figure
        """

        if len(data_names) != len(colors):
            raise IndexError('Кол-во цветов и графиков не совпадает')

        fig = figure(plot_width=width_, plot_height=300,
                     tools="box_zoom, wheel_zoom, pan, save, reset",
                     active_scroll="wheel_zoom", lod_threshold=100, x_axis_type="datetime")

        for fig_name, color in zip(data_names, colors):

            if ers == 'err':
                fig.add_layout(
                    Whisker(source=data_source, base="time", upper=fig_name+'_up_error', lower=fig_name+'_down_error'))
            elif ers == 'pretty':
                fig.add_layout(
                    Whisker(source=data_source, base="time", upper=fig_name+'_up_error', lower=fig_name+'_down_error',
                            line_color=color, lower_head=None, upper_head=None))

            fig.circle('time', fig_name, source=data_source, size=5, color=color,
                       nonselection_alpha=1, nonselection_color=color)

        fig.yaxis.axis_label = y_axis_name
        fig.xaxis.axis_label = 'Время'
        fig.xaxis.formatter = datetime_formatter
        fig.x_range = asym_fig.x_range

        return fig

    figs = [
        (create_fig(['y_one_l'], ['black'], 'Y [мм]', 'err'), 'Y ONE L'),
        (create_fig(['y_one_r'], ['black'], 'Y [мм]', 'err'), 'Y ONE R'),
        (create_fig(['y_cog_l'], ['black'], 'Y [мм]', 'err'), 'Y COG L'),
        (create_fig(['y_cog_r'], ['black'], 'Y [мм]', 'err'), 'Y COG R'),
        (create_fig(['rate' + i for i in ['_l', '_r']], ['red', 'blue'], 'Усл. ед.', 'pretty'), 'Rate'),
        (create_fig(['corrected_rate' + i for i in ['_l', '_r']], ['red', 'blue'], 'Усл. ед.', 'pretty'), 'Corr. rate'),
        (create_fig(['delta_rate'], ['black'], 'Корр. лев. - корр. пр.', 'err'), 'Delta corr. rate'),
        (create_fig(['charge'], ['blue'], 'Ед.'), 'Charge')
    ]

    tab_handler = Tabs(tabs=[Panel(child=fig, title=fig_name) for fig, fig_name in figs], width=width_)

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

    depol_start_stop_buttons.on_change(
        "active", lambda attr, old, new: (depolarizer.start_scan() if new == 0 else depolarizer.stop_scan()))

    # Подгонка

    fit_line_selection_widget = Select(title="Fitting line:", width=200, value=asym_renders[0].name,
                                       options=[(render.name, pretty_names[render.name]) for render in asym_renders])

    options = [name for name in fit.function_handler.keys()]
    if not options:
        raise IndexError("Пустой function_handler в fit.py")

    fit_function_selection_widget = Select(title="Fitting function:", value=options[0], options=options, width=200)

    fit_button = Button(label="FIT", width=200)

    def make_parameters_table(attr, old, new):
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
        if not fit_handler["fit_indices"]:
            return

        name = fit_function_selection_widget.value
        line_name = fit_line_selection_widget.value

        left_time_, right_time_ = fit_handler["fit_indices"]

        left_ind_ = bisect.bisect_left(data_source.data['time'], left_time_)
        right_ind_ = bisect.bisect_right(data_source.data['time'], right_time_, lo=left_ind_)

        if left_ind_ == right_ind_:
            return

        clear_fit()

        x_axis = data_source.data['time'][left_ind_:right_ind_]
        y_axis = data_source.data[line_name][left_ind_:right_ind_]
        y_errors = data_source.data[line_name + '_up_error'][left_ind_:right_ind_] - y_axis

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
        left_ = zone_of_interest.location
        x_time = x_axis - left_  # Привёл время в интервал от 0
        x_time /= time_coef             # Перевёл в секунды

        # Создание точек, которые передадутся в подогнанную функцию с параметрами,
        # и точек, которые соответсвуют реальным временам на графике (т.е. без смещения к 0)

        fit_line_real_x_axis = np.linspace(left_time_, right_time_, fit_line_points_amount)
        fit_line_x_axis = fit_line_real_x_axis - left_
        fit_line_x_axis /= time_coef

        m = fit.create_fit_func(name, x_time, y_axis, y_errors, kwargs)

        fit.fit(m)  # TODO: в отдельный поток?
        params_ = m.get_param_states()
        for param in params_:
            fit_handler["input_fields"][param['name']]["Init value"].value = str(param['value'])
            if param['name'] == "depol_time":
                freq = freq_storage_.find_closest_freq(param['value'] + left_ / time_coef - utc_plus_7h)
                freq_error = 0
                freq_error = abs(depolarizer.speed*param['error'])
                energy = depolarizer.frequency_to_energy(freq) if freq != 0 else 0
                energy_error = depolarizer.frequency_to_energy(freq_error, depolarizer._F0, 0)
                #energy_window.text = f"<p>Частота: {freq} +- {freq_error}, энергия: {energy}</p>"
                energy_window.text = "<p>Частота: %8.1f +- %.1f, \n Энергия: %7.3f +- %.1f</p>" % (freq, freq_error, energy, energy_error)

        fit_handler["fit_line"] = asym_fig.line(fit_line_real_x_axis,
                                                fit.get_line(name, fit_line_x_axis, [x['value'] for x in params_]),
                                                color="red", line_width=2)

    fit_button.on_click(fit_callback)

    # Инициализация bokeh app, расположение виджетов
    column_1 = column(gridplot([tab_handler], [asym_fig], merge_tools=False), period_input, width=width_ + 50)
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
    layout_ = layout([[column_1, column_2]])

    # Настройка документа Bokeh

    update_data()
    doc.add_periodic_callback(hist_update, 1000)         # TODO запихнуть в один callback
    doc.add_periodic_callback(update_data, 1000)         # TODO: подобрать периоды
    doc.add_periodic_callback(update_depol_status, 1000)
    doc.title = "Laser polarimeter"
    doc.add_root(layout_)
