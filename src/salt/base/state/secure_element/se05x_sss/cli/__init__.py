#
# Copyright 2019,2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

import os
import logging

from . import cli
from . import cli_get
from . import cli_set
from . import cli_generate
from . import cli_cloud
from . import cli_se05x
from . import cli_a71ch
from . import cli_refpem
from . import cli_policy

logging.basicConfig(level=logging.INFO)

# This is required to support click on imx
try:
    ENV_LANG = os.environ['LANG']
    if ENV_LANG is None:
        os.environ['LC_ALL'] = "en_US.utf-8"
        os.environ['LANG'] = "en_US.utf-8"
except Exception as exc:  # pylint: disable=broad-except
    os.environ['LC_ALL'] = "en_US.utf-8"
    os.environ['LANG'] = "en_US.utf-8"
