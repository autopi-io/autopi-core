import logging


log = logging.getLogger(__name__)


def help():
    """
    This command.
    """

    return __salt__["sys.doc"]("log.*")


def query(file, begin="^", end="$", match=".*", count=0, reverse=False, before=0, after=0, first=0, last=100):
    """
    Query a log file or any file.
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
