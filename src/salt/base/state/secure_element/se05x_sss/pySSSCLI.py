#
# Copyright 2018,2019 NXP
# SPDX-License-Identifier: Apache-2.0
#

import sys
import os
sss_dir = os.path.abspath(os.getcwd()
                                + os.sep + ".."
                                + os.sep + ".."
                                + os.sep + "pycli"
                                + os.sep + "src")
sys.path.append(sss_dir)
import cli

if __name__ == '__main__':
    cli.cli.cli(sys.argv[1:])
    #cli.cli.cli("a71ch reset".split())
    #cli.cli.cli("generate ecc 0x12322 256".split())
