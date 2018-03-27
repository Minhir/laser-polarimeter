from iminuit import Minuit, describe, Struct
from math import exp


class GenericChi2:
    def __init__(self, f, x, y, y_err):
        self.x = x
        self.y = y
        self.y_err = y_err
        self.f = f
        args = describe(f)  # extract function signature
        self.func_code = Struct(
                locals=args[1:],   # dock off independent param
                co_argcount=len(args)-1
            )

    def __call__(self, *arg):
        return sum(((self.f(x, *arg)-y) / y_err)**2 for x, y, y_err in zip(self.x, self.y, self.y_err))


def polarization(P0, Pmax, tau, t):
    return P0 + (Pmax-P0)*(1.0 - exp(- t/tau))


def const(time, p0):
    return p0


def exp_jump(time, depol_time, P0, Pmax, tau, DELTA, T):

    if time < depol_time - T / 2:
        return polarization(P0, Pmax, tau, time)

    P1 = polarization(P0, Pmax, tau, depol_time)  # polarization before jump

    if DELTA == -100:
        P2 = 0
    else:
        P2 = P1 + DELTA  # polarization after jump;

    if time < depol_time + T / 2:

        return P1 + (P2 - P1) * (time - depol_time + T / 2) / T

    return polarization(P2,Pmax, tau, time - depol_time)


def fit(x, y, y_err):
    m = Minuit(GenericChi2(exp_jump, x, y, y_err), depol_time=50, P0=0, Pmax=10, tau=14, DELTA=0, T=1)
    m.migrad()
    # m.print_param()
    return m

def get_line(x, params):
    return [exp_jump(i, *params) for i in x]
