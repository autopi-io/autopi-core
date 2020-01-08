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


def signal_strength(rated_only=False):
    """
    Get current signal strength values.

    Optional arguments:
      - rated_only (bool): Default is 'False'.
    """

    return qmilib.nas_get_signal_strength(rated_only=rated_only)


def system_info():
    """
    Get system info.
    """

    return qmilib.nas_get_system_info()
