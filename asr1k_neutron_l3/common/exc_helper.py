import inspect
import sys


class FakeTbFrame(object):
    def __init__(self, tb_frame, tb_lineno, tb_next):
        self.tb_frame = tb_frame
        self.tb_lineno = tb_lineno
        self.tb_next = tb_next


def exc_info_full():
    # save orig exception / tb info
    exc_type, exc, tb = sys.exc_info()

    for stack_frame in inspect.stack()[1:]:
        tb_frame = stack_frame[0]
        tb = FakeTbFrame(tb_frame, tb_frame.f_lineno, tb)

    return exc_type, exc, tb
