#!/usr/bin/env python
# -*- coding: utf-8 -*-

# ATTENTION: This file is managed by AutoPi and any manual changes may be overwritten during update!

from __future__ import print_function

import json
import re
import sys
import time
import urllib2  # 'requests' is slow to load so we use 'urllib2'
import uuid
import yaml

from collections import OrderedDict
from contextlib import closing
from retrying import retry


class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"

minion_id = None

def get_minion_id():
    global minion_id
    if not minion_id:
        with open("/etc/salt/minion_id", "r") as f:
            minion_id = uuid.UUID(f.read().strip())
    return minion_id

def retry_if_url_error(ex):
    if not isinstance(ex, urllib2.HTTPError):
        print(Colors.WARNING + "Local API not ready, retrying..." + Colors.ENDC)
        return isinstance(ex, urllib2.URLError)
    return False

@retry(retry_on_exception=retry_if_url_error, stop_max_attempt_number=30, wait_fixed=2000)
def execute(cmd, *args, **kwargs):
    url = "http://localhost:9000/dongle/{:}/execute/".format(get_minion_id())
    data = json.dumps({"command": cmd, "arg": args, "kwarg": kwargs})
    req = urllib2.Request(url, data, {"Content-Type": "application/json", "Content-Length": len(data) })
    with closing(urllib2.urlopen(req)) as res:
        return json.loads(res.read())

def state_output(res):
    errors = []

    state_results = OrderedDict(sorted(res.items(), key=lambda item:item[1]['__run_num__']))

    for key in state_results.keys():
        if res[key]["result"]:
            print("{:} [ OK   ] {:}: {:} {:}".format(Colors.OKGREEN, res[key].get("name", ""), res[key]["comment"], Colors.ENDC))
            print("")
        else:
            print("{:} [ FAIL ] {:}: {:} {:}".format(Colors.FAIL, res[key].get("name", ""), res[key]["comment"], Colors.ENDC))
            errors.append(res[key])
            print("")

    print("")

    if errors:
        print(Colors.FAIL + "Errors found" + Colors.ENDC)
    else:
        print (Colors.OKGREEN + "Success" + Colors.ENDC)

    succeded = len(res.keys()) - len(errors)
    print("Finished running {:} states, succeded: {:}, failed: {:}".format(len(res.keys()), succeded, len(errors)))

def try_eval(val):
    if val.lower() in ["true", "false", "yes", "no"]:
        return val.lower() in ["true", "yes"]

    try:
       return eval(val, {"__builtins__": None}, {})
    except:
        return val

def main():

    if len(sys.argv) < 2:
        print("Usage: {:} [options] <command> [arguments]".format(sys.argv[0]))
        return

    args = list(sys.argv)

    # Pop script name
    args.pop(0)

    # Pop command
    cmd = args.pop(0)

    # Parse arguments
    cmd_args = []
    cmd_kwargs = {}
    for arg in args:

        # Check if keyword argument
        if re.match("^[_\w\d]+=", arg):
            key, val = arg.split("=", 1)
            cmd_kwargs[key] = try_eval(val)
        else:
            cmd_args.append(try_eval(arg))

    try:
        res = execute(cmd, *cmd_args, **cmd_kwargs)
    except urllib2.HTTPError as e:
        response_text = e.read()
        code = e.code if e.code != 500 else ''
        try:
            response_dict = json.loads(response_text)
            response_text = yaml.safe_dump(response_dict, default_flow_style=False)
        except Exception:
            pass

        print(Colors.FAIL + code + response_text + Colors.ENDC, file=sys.stderr)
        return

    if cmd.startswith("state.") and isinstance(res,dict):
        state_output(res)
    else:
        print(yaml.safe_dump(res, default_flow_style=False))

if __name__ == "__main__":
    main()
