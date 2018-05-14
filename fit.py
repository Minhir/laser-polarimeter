from iminuit import Minuit, describe, Struct
from math import exp
import inspect
import numpy as np
import bottleneck as bn


class GenericChi2:
    def __init__(self, f, x, y, y_err):
        self.x = x
        self.y = y
        self.y_err = y_err
        self.f = f
        args = describe(f)  # extract function signature
        self.func_code = Struct(
                co_varnames=args[1:],   # dock off independent param
                co_argcount=len(args)-1
            )

    def __call__(self, *arg):
        f_res = np.array([self.f(x, *arg) for x in self.x])
        s = (f_res - self.y) / self.y_err
        return bn.ss(s)


def polarization(P0, Pmax, tau, t):
    return P0 + (Pmax-P0)*(1.0 - exp(- t/tau))


def const(time, p0=0):
    return p0


def exp_jump(time, depol_time=50, P0=0, Pmax=-10, tau=14, DELTA=10, T=1):

    if time < depol_time - T / 2:
        return polarization(P0, Pmax, tau, time)

    P1 = polarization(P0, Pmax, tau, depol_time)  # polarization before jump

    P2 = 0 if DELTA == -100 else P1 + DELTA

    if time < depol_time + T / 2:
        return P1 + (P2 - P1) * (time - depol_time + T / 2) / T

    return polarization(P2, Pmax, tau, time - depol_time)


# Хранит функции подгонки. У функции обязательно должны быть начальные значения параметров!
# Первый аргумент всегда time
function_handler = {"exp_jump": exp_jump,
                    "const": const}


def get_function_params(name):
    """Возвращает список пар (имя параметра, значение по умолчанию). Не включает параметр time"""
    x = inspect.signature(function_handler[name]).parameters
    return [(i, x[i].default) for i in x if i != 'time']


def create_fit_func(name, x, y, y_err, kwargs) -> Minuit:
    y_not_nan = ~np.isnan(y)
    y_ = y[y_not_nan]
    if y_.size == 0:
        raise ValueError("Нет валидных значений")
    x_ = x[y_not_nan]
    y_err_ = y_err[y_not_nan]
    return Minuit(GenericChi2(function_handler[name], x_, y_, y_err_), throw_nan=True, **kwargs)


def fit(m: Minuit):
    m.migrad()  # TODO: ncall=1000000 -- вынести в интерфейс?
    # m.hesse()
    return m


def get_line(name, x, params):
    """Прменяет функцию name с данными параметрами params к списку x"""
    return [function_handler[name](i, *params) for i in x]

