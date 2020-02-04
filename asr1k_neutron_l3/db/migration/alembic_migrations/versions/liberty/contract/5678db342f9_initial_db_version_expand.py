# Copyright 2017 SAP SE
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

"""ASR1K Initial db version

Revision ID: 5678db342f9
Create Date: 2017-11-13 12:37:34.38453

"""

from neutron.db.migration import cli

# revision identifiers, used by Alembic.
revision = '5678db342f9'
down_revision = None

branch_labels = (cli.EXPAND_BRANCH,)


def upgrade():
    pass