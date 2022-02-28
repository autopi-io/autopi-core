import logging
import re
import salt.exceptions


log = logging.getLogger(__name__)


def help():
    """
    Shows this help information.
    """

    return __salt__["sys.doc"]("log")


def query(file, begin="^", end="$", match=".*", count=0, reverse=False, before=0, after=0, first=0, last=100):
    """
    Query a log file or any text file.

    Arguments:
      - file (str): Path of log file.

    Optional arguments:
      - begin (str): Default is '^'.
      - end (str): Default is '$'.
      - match (str): Default is '.*'.
      - count (int): Default is '0'.
      - reverse (bool): Default is 'False'.
      - before (int): Default is '0'.
      - after (int): Default is '0'.
      - first (int): Default is '0'.
      - last (int): Default is '100'.
    """

    pipeline = []

    # Use 'zless' to unpack gz files
    pipeline.append("zless {:s}".format(file))

    # Use 'sed' to narrow down lines using 'begin' and/or 'end'
    pipeline.append("sed -n '{:s}{:s}'".format(
        "/{:s}/,".format(begin) if begin != "^" else "",
        "/{:s}/p".format(end)
    ))

    # Reverse before 'grep' if requested
    if reverse:
        pipeline.append("tac")

        # We need to swap 'before' and 'after' context
        swap = (before, after)[::-1]
        before, after = swap

    # Use 'grep' to match lines and get 'before' and 'after' context
    grep_args = []
    if before > 0:
        grep_args.append("-B{:d}".format(before))
    if after > 0:
        grep_args.append("-A{:d}".format(after))
    if count > 0:
        grep_args.append("-m{:d}".format(count))

    pipeline.append("grep -i {:s} '{:s}'".format(
        " ".join(grep_args),
        match
    ))

    # Reverse after 'grep' if requested
    if reverse:
        pipeline.append("tac")

    # Use 'head' to only get first lines
    if first > 0:
        pipeline.append("head -n{:d}".format(first))

    # Use 'tail' to only get last lines
    if last > 0:
        pipeline.append("tail -n{:d}".format(last))

    return __salt__["cmd.shell"](" | ".join(pipeline), output_loglevel="quiet")


def kernel(level="err", facilities=[], offset=None, clear=False):
    """
    Print and/or clear the kernel ring buffer.

    Optional arguments:
      - level (str): Restict output the the given level and higher. Default is 'err'.
      - facilities (str): Restrict output to the given list (comma-separated) of facilities.
      - offset (str): Offset regex to begin from.
      - clear (bool): Clear after reading.
    """

    DMESG_LEVELS = [
        "emerg",   # System is unusable
        "alert",   # Action must be taken immediately
        "crit",    # Critical conditions
        "err",     # Error conditions
        "warn",    # Warning conditions
        "notice",  # Normal but significant condition
        "info",    # Informational
        "debug"    # Debug-level messages
    ]

    DMESG_FACILITIES = [
        "kern",    # Kernel messages
        "user",    # Random user-level messages
        "mail",    # Mail system
        "daemon",  # System daemons
        "auth",    # Security/authorization messages
        "syslog",  # Messages generated internally by syslogd
        "lpr",     # Line printer subsystem
        "news"     # Network news subsystem
    ]

    ret = []

    pipeline = []

    dmesg_args = ["--time-format iso", "-x"]

    if level:
        if not level in DMESG_LEVELS:
            raise ValueError("Invalid level (supported levels are {:})".format(", ".join(DMESG_LEVELS)))

        dmesg_args.append("-l {:}".format(",".join(DMESG_LEVELS[:DMESG_LEVELS.index(level) + 1])))

    if facilities:
        if isinstance(facilities, str):
            facilities = facilities.split(",")

        for facility in facilities:
            if not facility in DMESG_FACILITIES:
                raise ValueError("Invalid facility '{:}' (supported facilities are {:})".format(facility, ", ".join(DMESG_FACILITIES)))

        dmesg_args.append("-f {:}".format(",".join(facilities)))

    if clear:
        dmesg_args.append("-c")

    pipeline.append("dmesg {:}".format(" ".join(dmesg_args)))

    if offset != None:
        pipeline.append("sed -n '/{:}/,/&/p'".format(offset))

    res = __salt__["cmd.shell"](" | ".join(pipeline))

    if not res:
        return ret

    # Compile regex here to avoid doing it when module is loaded
    regex = re.compile(  # NOTE: Cached if called multiple times
        "^(?P<facility>{facilities:}):(?P<level>{levels:}): (?P<timestamp>{time_format:}) (?P<message>.+?)(?=\Z|^({facilities:}):({levels:}): )".format(
            levels="|".join(["{: <6}".format(l) for l in DMESG_LEVELS]),
            facilities="|".join(["{: <6}".format(f) for f in DMESG_FACILITIES]),
            time_format="[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2},[0-9]{6}\+(?:[0-9]{4}|[0-9]{2}:[0-9]{2})"
        ),
        re.MULTILINE | re.DOTALL
    )

    for match in regex.finditer(res):
        ret.append({k: v.rstrip() for k, v in match.groupdict().iteritems()})

    if not ret:
        raise salt.exceptions.CommandExecutionError("Failed to parse dmesg result with pattern: {:}".format(regex.pattern))

    return ret


def kernel_iter(level="err", facilities=[], offset_key="timestamp", reset=False):
    """
    Helper function to retrieve new kernel log entries (based on cached offset value).

    Optional arguments:
      - level (str): Restict output the the given level and higher. Default is 'err'.
      - facilities (str): Restrict output to the given list (comma-separated) of facilities.
      - offset_key (str): Key to get value from result and use as offset. Default is 'timestamp'.
      - reset (bool): Reset cached offset value and start over.
    """

    ret = []

    ctx = __context__.setdefault("log.kernel_iter", {})

    if reset:
        ctx["offset"] = None

    offset = ctx.get("offset", None)

    res = kernel(level=level, facilities=facilities, offset=offset)
    if res:

        # Skip first log entry if offset was defined (bacause offset entry is included in result)
        if offset != None:
            ret = res[1:]
        else:
            ret = res

        # Update offset using last log entry
        ctx["offset"] = res[-1][offset_key]

    return ret
