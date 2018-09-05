#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import sys
import time
import urllib2  # 'requests' is slow to load so we use 'urllib2'
import uuid
import yaml

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
    return isinstance(ex, urllib2.URLError)

@retry(retry_on_exception=retry_if_url_error, stop_max_attempt_number=30, wait_fixed=2000)
def execute(cmd, *args, **kwargs):
    url = "http://localhost:9000/dongle/{:}/execute/".format(get_minion_id())
    data = json.dumps({"command": cmd, "arg": args, "kwarg": kwargs})
    req = urllib2.Request(url, data, {"Content-Type": "application/json", "Content-Length": len(data) })    
    with closing(urllib2.urlopen(req)) as res:
        return json.loads(res.read())

def state_output(res):
    errors = []

    for key in res.keys():
        if res[key]["result"]:
            print(u"{:} \u2714 {:}{:}".format(Colors.OKGREEN, res[key]["comment"], Colors.ENDC))
        else:
            print(u"{:} \u2718 {:}{:}".format(Colors.FAIL, res[key]["comment"], Colors.ENDC))
            errors.append(res[key])

    print("")

    if errors:
        print (Colors.FAIL + "Error details" + Colors.ENDC)
        for error in errors:
            print("{:}{:}{:}".format(Colors.FAIL, json.dumps(error, indent=4), Colors.ENDC))
        print("")
    else:
        print (Colors.OKGREEN + "Success" + Colors.ENDC)

    succeded = len(res.keys()) - len(errors)
    print("Finished running {:} states, succeded: {:}, failed: {:}".format(len(res.keys()), succeded, len(errors)))

def main():

    if len(sys.argv) < 2:
        print("Usage: {:} [options] <command> [arguments]".format(sys.argv[0]))
        return

    # Pop script name
    sys.argv.pop(0)

    # Pop command
    cmd = sys.argv.pop(0)

    # Parse arguments
    args = []
    kwargs = {}
    for arg in sys.argv:
        if "=" in arg:
            key, val = arg.split("=", 1)
            kwargs[key] = val
        else:
            args.append(arg)

    res = execute(cmd, *args, **kwargs)

    if cmd.startswith("state."):
        state_output(res)
    else:
        print(yaml.safe_dump(res, default_flow_style=False))

if __name__ == "__main__":
    main()