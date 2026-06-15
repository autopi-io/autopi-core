import logging
import psutil
import re

import command_util as cutil
from command_util import normalizers
from common_util import dict_query, pretty_size
from messaging import EventDrivenMessageClient, msg_pack as _msg_pack


DISK_HOUSEKEEPER_NAMESPACE = "disk_housekeeper"

__virtualname__ = "logger"

log = logging.getLogger(__name__)

client = EventDrivenMessageClient(__virtualname__)


def __virtual__():
    return __virtualname__


def __init__(opts):
    client.init(opts)


def help():
    """
    Shows this help information.
    """

    return __salt__["sys.doc"](__virtualname__)


def channel_namespaces(*only):
    """
    Returns available namespaces grouped by the channel they belong to.

    Arguments:
      - *only (str): The channel(s) to include in the result. If none defined all channels are included.
    """

    ret = {}

    ns_regex = re.compile("^(?P<interface>can[0-9]+)(?:_.+)?$")
    for engine in __salt__["config.get"]("engines", []):
        for key in engine.keys():
            ns = engine[key].get("namespace", "")
            match = ns_regex.match(ns)
            if match:
                interface = match.group("interface")

                if only:
                    if not interface in only:
                        continue

                ret.setdefault(interface, []).append(ns)

    return ret


def status(**kwargs):
    """
    Returns a status overview of all channels and disks available for this device.
    This command is just a composite result of the two commands 'logger.channels' and 'logger.disks'.

    Optional arguments:
      - verbose (bool): Include more details in the result? Default value is 'False'.
    """

    try:
        return {
            "channels": channels(**kwargs),
            "disks": disks(**kwargs),
        }
    except:
        log.exception("Failed to gather logger status")
        raise


def channel(*args, **kwargs):
    """
    Alias for the 'logger.channels' command.
    """

    return channels(*args, **kwargs)


def channels(*only, **kwargs):
    """
    Returns details of all channels available for this device.

    Arguments:
      - *only (str): The channel(s) to include in the result. If none defined all channels are included.

    Optional arguments:
      - verbose (bool): Include more details in the result? Default value is 'False'.
    """

    ret = {}

    sanitize = kwargs.pop("sanitize", True)
    cutil.sanitize_kwargs(sanitize, kwargs, [
        ("verbose", False,  normalizers.boolean,    [],()),
    ])
    verbose = kwargs.pop("verbose")

    data = {}
    interface_namespaces = channel_namespaces(*only)
    for interface, namespaces in interface_namespaces.iteritems():
        for ns in namespaces:
            try:
                data[ns] = client.send_sync(_msg_pack("insight", _workflow="manage"), namespace=ns)
            except:
                data[ns] = {"[ERROR]": "Failed getting insight for namespace '{}'".format(ns)}

                log.exception("Failed getting insight for namespace '{}'".format(ns))

    for interface_name in interface_namespaces.keys():

        if "[ERROR]" in data.get(interface_name, {}):
            ret[interface_name] = data[interface_name]
            continue

        ret[interface_name] = {}

        # Add interface if available
        ret[interface_name]["interface"] = {}
        interface = dict_query(data, "{namespace:}:context:connections:{connection_name:}:interface", namespace=interface_name, connection_name=interface_name, raise_on_not_found=False, default={})
        if interface:
            ret[interface_name]["interface"]["bitrate"] = dict_query(interface, "bitrate")
            dbitrate = dict_query(data, "dbitrate", raise_on_not_found=False)
            if dbitrate:
                ret[interface_name]["interface"]["dbitrate"] = dbitrate

            fixed_bitrate = dict_query(data, "{namespace:}:context:connections:{connection_name:}:settings:fixed_bitrate", namespace=interface_name, connection_name=interface_name, raise_on_not_found=False, default=None)
            if fixed_bitrate:
                ret[interface_name]["interface"]["is_fixed_bitrate"] = True
            else:
                ret[interface_name]["interface"]["autodetect"] = dict_query(data, "{namespace:}:context:connections:{connection_name:}:autodetect", namespace=interface_name, connection_name=interface_name, raise_on_not_found=False, default={})
                if verbose:
                    ret[interface_name]["interface"]["autodetect"]["try_bitrates"] = dict_query(data, "{namespace:}:context:connections:{connection_name:}:settings:autodetect_try_bitrates", namespace=interface_name, connection_name=interface_name, raise_on_not_found=False, default=[])
        else:
            ret[interface_name]["interface"]["[WARNING]"] = "The interface is not connected at this time."

            continue  # TODO HN: For now we just skip because loggers are based on buses

        ret[interface_name]["loggers"] = {}

        # Add loggers based on available dump jobs
        dump_jobs = dict_query(data, "{namespace:}:context:external_dump:{connection_name:}:jobs", namespace=interface_name, connection_name=interface_name, raise_on_not_found=False, default={})
        for dump_job in dump_jobs.values():
            logger_name = dump_job["name"].split("/")[-1]

            ret[interface_name]["loggers"][logger_name] = {}
            ret[interface_name]["loggers"][logger_name]["received_frames_count"] = dict_query(dump_job, "total_frame_count")

            current_runner = dump_job.get("current_runner", {})
            if current_runner:
                ret[interface_name]["loggers"][logger_name]["current_fps"] = round(dict_query(current_runner, "stats:fps:current"), 2) 
                ret[interface_name]["loggers"][logger_name]["output_file"] = dict_query(current_runner, "settings:log_file", raise_on_not_found=False, default=None) or dict_query(current_runner, "settings:out_file")

                if verbose:
                    ret[interface_name]["loggers"][logger_name]["average_fps"] = round(dict_query(current_runner, "stats:fps:avg"), 2)
            else:
                ret[interface_name]["loggers"][logger_name]["current_fps"] = 0.0

                if verbose:
                    ret[interface_name]["loggers"][logger_name]["average_fps"] = 0.0

            dropped_frames_count = dict_query(dump_job, "total_frame_drop_count")
            if dropped_frames_count or verbose:
                ret[interface_name]["loggers"][logger_name]["dropped_frames_count"] = dropped_frames_count

            filters = dict_query(dump_job, "settings:runner:filters", raise_on_not_found=False, default=[])
            if filters:
                if verbose:
                    ret[interface_name]["loggers"][logger_name]["filters"] = filters  # TODO HN: Remove prefixed interface 'can0,'?
                else:
                    ret[interface_name]["loggers"][logger_name]["filters_count"] = len(filters)

            worker_name = "logger/{}".format(logger_name)
            worker_state = dict_query(data, "{namespace:}:workers:{worker_name:}:state", namespace=interface_name, worker_name=worker_name)
            if not worker_state == "running":
                ret[interface_name]["loggers"][logger_name]["worker_state"] = worker_state

        # Or add loggers based on available connection buses
        buses = dict_query(data, "{namespace:}:context:connections:{connection_name:}:buses", namespace=interface_name, connection_name=interface_name)
        if not buses and not ret[interface_name]["loggers"]:
            ret[interface_name]["loggers"]["[WARNING]"] = "No available buses nor jobs found at this time."

        file_handlers = dict_query(data, "{namespace:}:context:connections:{connection_name:}:file_handlers", namespace=interface_name, connection_name=interface_name)
        for bus_name in buses.keys():
            logger_name = re.sub("^wf_", "", bus_name)

            # Skip if we do not have a valid logger for this bus
            worker_name = "logger/{}".format(logger_name)
            logger_worker = dict_query(data, "{namespace:}:workers:{worker_name:}", namespace=interface_name, worker_name=worker_name, raise_on_not_found=False, default={})
            if not logger_worker or not [msg for msg in logger_worker.get("messages", []) if msg.get("handler", "") == "dump"]:
                continue

            ret[interface_name]["loggers"][logger_name] = {}
            ret[interface_name]["loggers"][logger_name]["current_fps"] = round(dict_query(buses, "{bus_name:}:stats:current_fps", bus_name=bus_name), 2)
            ret[interface_name]["loggers"][logger_name]["received_frames_count"] = dict_query(buses, "{bus_name:}:stats:rx", bus_name=bus_name)

            for full_output_file_pattern, file_handler in file_handlers.items():
                if file_handler.get("extra", {}).get("bus_ref", "") == logger_name:
                    ret[interface_name]["loggers"][logger_name]["output_file_pattern"] = full_output_file_pattern
                    break

            sent_frames_count = dict_query(buses, "{bus_name:}:stats:tx", bus_name=bus_name)
            if sent_frames_count or verbose:
                ret[interface_name]["loggers"][logger_name]["sent_frames_count"] = sent_frames_count

            received_error_frames_count = dict_query(buses, "{bus_name:}:stats:error_frame", bus_name=bus_name)
            if received_error_frames_count or verbose:
                ret[interface_name]["loggers"][logger_name]["received_error_frames_count"] = received_error_frames_count

            filters = dict_query(buses, "{bus_name:}:filters", bus_name=bus_name)
            if filters:
                if verbose:
                    ret[interface_name]["loggers"][logger_name]["filters"] = filters
                else:
                    ret[interface_name]["loggers"][logger_name]["filters_count"] = len(filters)

            if verbose:
                ret[interface_name]["loggers"][logger_name]["average_fps"] = round(dict_query(buses, "{bus_name:}:stats:avg_fps", bus_name=bus_name), 2)

            worker_name = "logger/{}".format(logger_name)
            worker_state = dict_query(data, "{namespace:}:workers:{worker_name:}:state", namespace=interface_name, worker_name=worker_name)
            if not worker_state == "running":
                ret[interface_name]["loggers"][logger_name]["worker_state"] = worker_state

        # Finally loop through all loggers and append decoders and output handlers
        for logger_name in ret[interface_name]["loggers"].keys():

            def get_output_handlers_for(sync_job_ref_name_regex):
                ret = []

                s3_uploader_ns = "{}_s3_uploader".format(interface_name)
                if s3_uploader_ns in data:
                    if not data[s3_uploader_ns].get("context", None):
                        return {"[WARNING]": "Data not yet available - please wait and try again later."}

                    sync_jobs = dict_query(data, "{namespace:}:context:{logger_name:}_logger_uploader:jobs", namespace=s3_uploader_ns, logger_name=logger_name)
                    if sync_jobs:
                        for sync_job in filter(lambda j: re.match(sync_job_ref_name_regex, j.get("ref_name", "")), sync_jobs):
                            output_handler = {
                                "destination_path": dict_query(sync_job, "settings:destination"),
                                "uploaded_files_count": dict_query(sync_job, "uploaded_files_count"),
                            }
                            if sync_job["seen_errors"]:
                                if verbose:
                                    output_handler["seen_errors"] = sync_job["seen_errors"]
                                else:
                                    output_handler["seen_errors_count"] = sum(sync_job["seen_errors"].values())

                            if verbose:
                                output_handler["type"] = dict_query(sync_job, "type")
                                output_handler["state"] = dict_query(sync_job, "state")
                                output_handler["completed_cycles_count"] = dict_query(sync_job, "state_count:completed", raise_on_not_found=False, default=0)
                                output_handler["source_path"] = dict_query(sync_job, "settings:source")

                            ret.append(output_handler)

                return ret

            # Add output handlers
            sync_job_ref_name_regex = "^{interface_name:}/logger/{logger_name:}/output_handler/.+".format(interface_name=interface_name, logger_name=logger_name)
            output_handlers = get_output_handlers_for(sync_job_ref_name_regex)
            if output_handlers:
                ret[interface_name]["loggers"][logger_name]["output_handlers"] = output_handlers

            # Add decoders
            decoder_ns = "{}_decoder".format(interface_name)
            if "[ERROR]" in data.get(decoder_ns, {}):
                ret[interface_name]["loggers"][logger_name]["decoders"] = data[decoder_ns]
                continue

            decoders = dict_query(data, "{namespace:}:context", namespace=decoder_ns, raise_on_not_found=False, default={})
            if not decoders:
                continue

            ret[interface_name]["loggers"][logger_name]["decoders"] = {}
            for logger_decoder_name in decoders.keys():
                decoder_name = re.sub("^{logger_name:}_".format(logger_name=logger_name), "", logger_decoder_name)

                ret[interface_name]["loggers"][logger_name]["decoders"][decoder_name] = {}
                ret[interface_name]["loggers"][logger_name]["decoders"][decoder_name]["type"] = dict_query(decoders, "{logger_decoder_name}:decoder", logger_decoder_name=logger_decoder_name)

                ret[interface_name]["loggers"][logger_name]["decoders"][decoder_name]["total_messages_count"] = dict_query(decoders, "{logger_decoder_name}:total_message_count", logger_decoder_name=logger_decoder_name)
                decoded_messages_count = dict_query(decoders, "{logger_decoder_name}:decoded_message_count", logger_decoder_name=logger_decoder_name)
                if decoded_messages_count:
                    ret[interface_name]["loggers"][logger_name]["decoders"][decoder_name]["decoded_messages_count"] = decoded_messages_count
                failed_messages_count = dict_query(decoders, "{logger_decoder_name}:failed_message_count", logger_decoder_name=logger_decoder_name)
                if failed_messages_count:
                    ret[interface_name]["loggers"][logger_name]["decoders"][decoder_name]["failed_messages_count"] = failed_messages_count

                ret[interface_name]["loggers"][logger_name]["decoders"][decoder_name]["output_file_pattern"] = dict_query(decoders, "{logger_decoder_name}:output_format", logger_decoder_name=logger_decoder_name)

                if verbose:
                    ret[interface_name]["loggers"][logger_name]["decoders"][decoder_name]["library_file_path"] = dict_query(decoders, "{logger_decoder_name}:library_file_path", logger_decoder_name=logger_decoder_name)
                    ret[interface_name]["loggers"][logger_name]["decoders"][decoder_name]["input_path"] = dict_query(decoders, "{logger_decoder_name}:input_path", logger_decoder_name=logger_decoder_name)

                worker_name = "logger/{}/decoder/{}".format(logger_name, decoder_name)
                worker_state = dict_query(data, "{namespace:}:workers:{worker_name:}:state", namespace=decoder_ns, worker_name=worker_name)
                if not worker_state == "running":
                    ret[interface_name]["loggers"][logger_name]["decoders"][decoder_name]["worker_state"] = worker_state

                # Add output handlers
                sync_job_ref_name_regex = "^{interface_name:}/logger/{logger_name:}/decoder/{decoder_name:}/output_handler/.+".format(interface_name=interface_name, logger_name=logger_name, decoder_name=decoder_name)
                output_handlers = get_output_handlers_for(sync_job_ref_name_regex)
                if output_handlers:
                    ret[interface_name]["loggers"][logger_name]["decoders"][decoder_name]["output_handlers"] = output_handlers

        # TODO HN: Consider to add:
        #ret[interface_name]["output_handler_worker_state"] =

        # Add frame listeners
        dump_match_jobs = dict_query(data, "{namespace:}:context:external_dump_match:{connection_name:}:jobs", namespace=interface_name, connection_name=interface_name, raise_on_not_found=False, default={})
        for dump_match_job in dump_match_jobs.values():
            frame_listener_name = dump_match_job["name"].split("/")[-1]

            ret[interface_name].setdefault("frame_listeners", {})[frame_listener_name] = {}
            ret[interface_name]["frame_listeners"][frame_listener_name]["matched_frames_count"] = dict_query(dump_match_job, "settings:runner:on_line_callbacks:frame:match:success_count", raise_on_not_found=False, default=0)
            ret[interface_name]["frame_listeners"][frame_listener_name]["received_frames_count"] = dict_query(dump_match_job, "total_frame_count")

            dropped_frames_count = dict_query(dump_match_job, "total_frame_drop_count")
            if dropped_frames_count or verbose:
                ret[interface_name]["frame_listeners"][frame_listener_name]["dropped_frames_count"] = dropped_frames_count

            _, id_filter_string = dict_query(dump_match_job, "settings:runner:filters")[0].split(",")
            ret[interface_name]["frame_listeners"][frame_listener_name]["id_filter"] = id_filter_string

            match_data = dict_query(dump_match_job, "settings:runner:on_line_callbacks:frame:match:data", raise_on_not_found=False, default="")
            match_data_mask = dict_query(dump_match_job, "settings:runner:on_line_callbacks:frame:match:data_mask", raise_on_not_found=False, default="")
            if match_data and match_data_mask:
                ret[interface_name]["frame_listeners"][frame_listener_name]["data_filter"] = "{}:{}".format(match_data, match_data_mask)

            match_eval = dict_query(dump_match_job, "settings:runner:on_line_callbacks:frame:match:eval", raise_on_not_found=False, default="")
            if match_eval:
                if verbose:
                    ret[interface_name]["frame_listeners"][frame_listener_name]["match_eval"] = match_eval
                else:
                    ret[interface_name]["frame_listeners"][frame_listener_name]["has_match_eval"] = True

            seen_errors = dict_query(dump_match_job, "settings:runner:on_line_callbacks:frame:seen_errors", raise_on_not_found=False, default={})
            if seen_errors:
                if verbose:
                    ret[interface_name]["frame_listeners"][frame_listener_name]["seen_errors"] = seen_errors
                else:
                    ret[interface_name]["frame_listeners"][frame_listener_name]["seen_errors_count"] = sum(seen_errors.values())

            worker_name = "frame_listener/{}".format(frame_listener_name)
            worker_state = dict_query(data, "{namespace:}:workers:{worker_name:}:state", namespace=interface_name, worker_name=worker_name)
            if not worker_state == "running":
                ret[interface_name]["frame_listeners"][frame_listener_name]["worker_state"] = worker_state

        # Add queries
        for worker_name, worker_data in dict_query(data, "{namespace:}:workers", namespace=interface_name, raise_on_not_found=False, default={}).iteritems():
            query_name = worker_name.split("/")[-1]

            if worker_name.startswith("query/raw/"):
                ret[interface_name].setdefault("queries", {})[query_name] = {
                    "type": "raw"
                }

                def build_req_dict(worker_message):
                    ret = {}

                    pass_filters = dict_query(worker_message, "kwargs:pass_filters", raise_on_not_found=False, default=[])

                    if verbose:
                        ret["frames"] = dict_query(worker_message, "args")
                        ret["pass_filters"] = pass_filters

                        last_result = dict_query(worker_message, "context:last_result", raise_on_not_found=False, default=None)
                        if last_result:
                            ret["last_result"] = last_result

                    else:
                        ret["frames_count"] = len(dict_query(worker_message, "args"))
                        ret["pass_filters_count"] = len(pass_filters)

                    return ret

                worker_messages = dict_query(worker_data, "messages")
                if len(worker_messages) == 1:
                    ret[interface_name]["queries"][query_name]["request"] = build_req_dict(worker_messages[0])
                else:
                    for worker_message in worker_messages:
                        ret[interface_name]["queries"][query_name].setdefault("requests", []).append(build_req_dict(worker_message))

            elif worker_name.startswith("query/obd/"):
                ret[interface_name].setdefault("queries", {})[query_name] = {
                    "type": "obd"
                }

                def build_pid_dict(worker_message):
                    ret = {
                        "name": dict_query(worker_message, "args")[0]
                    }

                    arb_id = dict_query(worker_message, "kwargs:id", raise_on_not_found=False, default=None)
                    if arb_id:
                        ret["id"] = arb_id

                    mode = dict_query(worker_message, "kwargs:mode", raise_on_not_found=False, default=None)
                    if mode:
                        ret["mode"] = mode

                    pid = dict_query(worker_message, "kwargs:pid", raise_on_not_found=False, default=None)
                    if pid:
                        ret["code"] = pid

                    last_result = dict_query(worker_message, "context:last_result", raise_on_not_found=False, default=None)
                    if last_result:
                        ret["last_result"] = last_result

                    return ret

                worker_messages = dict_query(worker_data, "messages")
                if len(worker_messages) == 1:
                    if verbose:
                        ret[interface_name]["queries"][query_name]["pid"] = build_pid_dict(worker_messages[0])
                    else:
                        ret[interface_name]["queries"][query_name]["pid"] = dict_query(worker_messages[0], "args")[0]
                else:
                    for worker_message in worker_messages:
                        if verbose:
                            ret[interface_name]["queries"][query_name].setdefault("pids", []).append(build_pid_dict(worker_message))
                        else:
                            ret[interface_name]["queries"][query_name].setdefault("pids", []).append(dict_query(worker_message, "args")[0])

            elif worker_name.startswith("query/j1939/"):
                ret[interface_name].setdefault("queries", {})[query_name] = {
                    "type": "j1939"
                }

                def build_pgn_dict(worker_message):
                    ret = {
                        "name": dict_query(worker_message, "kwargs:name"),
                        "code": dict_query(worker_message, "args")[0]
                    }

                    last_result = dict_query(worker_message, "context:last_result", raise_on_not_found=False, default=None)
                    if last_result:
                        ret["last_result"] = last_result

                    return ret

                worker_messages = dict_query(worker_data, "messages")
                if len(worker_messages) == 1:
                    if verbose:
                        ret[interface_name]["queries"][query_name]["pgn"] = build_pgn_dict(worker_messages[0])
                    else:
                        ret[interface_name]["queries"][query_name]["pgn"] = dict_query(worker_messages[0], "kwargs:name")
                else:
                    for worker_message in worker_messages:
                        if verbose:
                            ret[interface_name]["queries"][query_name].setdefault("pgns", []).append(build_pgn_dict(worker_message))
                        else:
                            ret[interface_name]["queries"][query_name].setdefault("pgns", []).append(dict_query(worker_message, "kwargs:name"))
            else:

                # Skip because unsupported type
                continue

            # Common for all query types:

            ret[interface_name]["queries"][query_name]["loop_count"] = dict_query(worker_data, "loop_count", raise_on_not_found=False, default=0)

            if worker_data.get("seen_warnings", {}):
                if verbose:
                    ret[interface_name]["queries"][query_name]["seen_warnings"] = worker_data["seen_warnings"]
                else:
                    ret[interface_name]["queries"][query_name]["seen_warnings_count"] = sum(worker_data["seen_warnings"].values())

            if worker_data.get("seen_errors", {}):
                if verbose:
                    ret[interface_name]["queries"][query_name]["seen_errors"] = worker_data["seen_errors"]
                else:
                    ret[interface_name]["queries"][query_name]["seen_errors_count"] = sum(worker_data["seen_errors"].values())

            worker_state = dict_query(worker_data, "state")
            if not worker_state == "running":
                ret[interface_name]["queries"][query_name]["worker_state"] = worker_state

        # Add event reactors
        for event_reactor in dict_query(data, "{namespace:}:reactors", namespace=interface_name, raise_on_not_found=False, default=[]):
            event_reactor_name = event_reactor["name"]

            # Skip if system event reactor and not verbose
            if event_reactor_name.startswith("_") and not verbose:
                continue

            ret[interface_name].setdefault("event_reactors", {})[event_reactor_name] = {
                "tag_regex": event_reactor["regex"],
                "hit_count": dict_query(event_reactor, "stats:match_count")
            }

            conditions = event_reactor.get("conditions", [])
            if conditions:
                if verbose:
                    ret[interface_name]["event_reactors"][event_reactor_name]["conditions"] = conditions
                else:
                    ret[interface_name]["event_reactors"][event_reactor_name]["conditions_count"] = len(conditions)

    return ret


def disk(*args, **kwargs):
    """
    Alias for the 'logger.disks' command.
    """

    return disks(*args, **kwargs)


def disks(**kwargs):
    """
    Returns details of all disks available for this device.

    Optional arguments:
      - verbose (bool): Include more details in the result? Default value is 'False'.
    """

    ret = {}

    sanitize = kwargs.pop("sanitize", True)
    cutil.sanitize_kwargs(sanitize, kwargs, [
        ("verbose", False,  normalizers.boolean,    [],()),
    ])
    verbose = kwargs.pop("verbose")

    # Check if the namespace is defined in the engines configuration
    ns = None
    for engine in __salt__["config.get"]("engines", []):
        for key in engine.keys():
            if engine[key].get("namespace", "") == DISK_HOUSEKEEPER_NAMESPACE:
                ns = DISK_HOUSEKEEPER_NAMESPACE
    if not ns:
        return {"[ERROR]": "The namespace '{}' does not exist in the configuration".format(DISK_HOUSEKEEPER_NAMESPACE)}

    data = client.send_sync(_msg_pack("insight", _workflow="manage"), namespace=ns)
    
    if not data.get("context", {}).get(DISK_HOUSEKEEPER_NAMESPACE, {}):
        return {"[WARNING]": "Data not yet available - please wait and try again later."}

    for disk_path, details in data.get("context", {}).get(DISK_HOUSEKEEPER_NAMESPACE, {}).iteritems():
        usage = psutil.disk_usage(disk_path)

        ret[disk_path] = {}
        ret[disk_path]["free_space"] = pretty_size(usage.free)
        if verbose:
            ret[disk_path]["used_space"] = pretty_size(usage.used)
            ret[disk_path]["total_capacity"] = pretty_size(usage.total)

        ret[disk_path]["housekeeper"] = {}
        ret[disk_path]["housekeeper"]["total_space_freed"] = pretty_size(dict_query(details, "total_space_freed"))
        ret[disk_path]["housekeeper"]["deleted_files_count"] = dict_query(details, "deleted_files_count")
        if verbose:
            ret[disk_path]["housekeeper"]["previous_space_freed"] = pretty_size(dict_query(details, "previous_space_freed"))
            ret[disk_path]["housekeeper"]["cleanup_size_threshold"] = pretty_size(dict_query(details, "size_limit"))
            ret[disk_path]["housekeeper"]["cleanup_critical_size_threshold"] = pretty_size(dict_query(details, "ciritcal_size_limit"))
            ret[disk_path]["housekeeper"]["cleanup_target_space_usage"] = pretty_size(dict_query(details, "target_space_usage"))
            ret[disk_path]["housekeeper"]["cleanup_folders"] = dict_query(details, "folders")

    return ret


def call(*args, **kwargs):
    """
    Helper command to call handlers or workflows on different engines/services identified by their namespace.

    Arguments:
      - namespace (str): The namespace of the engine/service to call.
      - handler/workflow (str): Name of the handler or workflow to call.
      - *args (str): The argument(s) to pass to the handler or workflow.

    Examples:
      - 'logger.call can0 manage context'
      - 'logger.call can0 obd_query rpm'
      - 'logger.call can0_decoder manage worker list'
    """

    ret = {}

    all_namespaces = []
    for interface, namespaces in channel_namespaces().iteritems():
        all_namespaces.extend(namespaces)
    for engine in __salt__["config.get"]("engines", []):
        for key in engine.keys():
            if engine[key].get("namespace", "") == DISK_HOUSEKEEPER_NAMESPACE:
                all_namespaces.append(DISK_HOUSEKEEPER_NAMESPACE)

    if not args:
        ret["supported_namespaces"] = all_namespaces
        return ret

    if len(args) < 1:
        raise ValueError("A namespace must be defined as the first argument")
    namespace = args[0]

    if not namespace in all_namespaces:
        raise ValueError("The specified namespace '{}' is not supported".format(namespace))

    if len(args) < 2:
        raise ValueError("A handler must be defined as the second argument")
    handler = args[1]

    args = args[2:]
    if handler == "manage":
        ret = client.send_sync(_msg_pack(*args, _workflow="manage", **kwargs), namespace=namespace)
    else:
        ret = client.send_sync(_msg_pack(*args, _handler=handler, **kwargs), namespace=namespace)

    return ret
