import logging
import qmilib


log = logging.getLogger(__name__)


def help():
    """
    Shows this help information.
    """

    return __salt__["sys.doc"]("qmi")


def cell_info():
    """
    Get cell location info.
    """

    return qmilib.nas_get_cell_location_info()


def connection_status():
    """
    Get packet service status.
    """

    return qmilib.wds_get_packet_service_status()


def connection_stats():
    """
    Get packet statistics.
    """

    return qmilib.wds_get_packet_statistics()


def operator_name():
    """
    Get operator name data.
    """

    return qmilib.nas_get_operator_name()


def serving_system():
    """
    Get serving system.
    """

    return qmilib.nas_get_serving_system()


def signal_strength(rated_only=False, include_desc=True):
    """
    Get current signal strength values.

    Optional arguments:
      - rated_only (bool): Default is 'False'.
      - include_desc (bool): Default is 'True'.
    """

    return qmilib.nas_get_signal_strength(rated_only=rated_only, include_desc=include_desc)


def system_info():
    """
    Get system info.
    """

    return qmilib.nas_get_system_info()
