# Copyright 2019 SAP SE
#
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
import inspect
import sys


class FakeTbFrame(object):
    def __init__(self, tb_frame, tb_lineno, tb_next):
        self.tb_frame = tb_frame
        self.tb_lineno = tb_lineno
        self.tb_next = tb_next


def exc_info_full(exc_type=None, exc_descr=None, skip=1):
    # save orig exception / tb info
    orig_exc_type, orig_exc, tb = sys.exc_info()
    exc_type = exc_type if exc_type is not None else orig_exc_type
    exc_descr = exc_descr if exc_descr is not None else orig_exc

    for stack_frame in inspect.stack()[skip:]:
        tb_frame = stack_frame[0]
        tb = FakeTbFrame(tb_frame, tb_frame.f_lineno, tb)

    return exc_type, exc_descr, tb
