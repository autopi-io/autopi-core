#
# Copyright 2018-2020 NXP
# SPDX-License-Identifier: Apache-2.0
#
#

"""License text"""

import os

if True:  # pylint: disable=using-constant-test
    TOOLS_DIR = os.path.abspath(os.path.dirname(__file__)
                                + os.sep + ".."
                                + os.sep + ".."
                                + os.sep + ".."
                                + os.sep + "tools")

    os.environ['PATH'] = TOOLS_DIR + os.pathsep + os.environ['PATH']

    if 'nt' == os.name and os.path.exists(r"C:\Mingw\bin"):  # pylint: disable=misplaced-comparison-constant
        os.environ['PATH'] = os.environ['PATH'] + os.pathsep + r"C:\Mingw\bin"

    if "DYLD_LIBRARY_PATH" in os.environ:
        os.environ['DYLD_LIBRARY_PATH'] = TOOLS_DIR + \
                                          os.pathsep + os.environ['DYLD_LIBRARY_PATH']
    else:
        os.environ['DYLD_LIBRARY_PATH'] = TOOLS_DIR + os.pathsep + "."

    if 'posix' == os.name:  # pylint: disable=misplaced-comparison-constant
        if "LD_LIBRARY_PATH" in os.environ:
            os.environ['LD_LIBRARY_PATH'] = TOOLS_DIR + \
                                            os.pathsep + os.environ['LD_LIBRARY_PATH']
        else:
            os.environ['LD_LIBRARY_PATH'] = TOOLS_DIR + os.pathsep + "."

    from . import session
    from . import plugandtrust_ver
    from . import genkey
    from . import sss_api
    from . import util
    from . import erasekey
    from . import policy
    from . import prepare_host_session
