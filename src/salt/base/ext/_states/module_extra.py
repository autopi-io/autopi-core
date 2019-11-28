import salt_more


def configured(name, args=[], kwargs={}):
    """
    Generic state to configure module function by convention.

    The convention is:
      - 'name' is the module + function (dot separated). 
      - 'args' are additional arguments but they are not allowed to perform any changes when specified.
      - 'kwargs' are the settings that needs to be configured. If not specifed the module should query current settings.
    """

    ret = {
        "name": name,
        "result": None,
        "changes": {},
        "comment": ""
    }

    res = salt_more.call_error_safe(__salt__["{:s}".format(name)], *args)
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to get current configuration: {:}".format(res["error"])
        return ret

    old = {k: v for k, v in list(res.items()) if not k.startswith("_")}
    new = kwargs

    if cmp(old, new) == 0:
        ret["result"] = True
        ret["comment"] = "Configuration is already up-to-date"
        return ret

    if __opts__["test"]:
        ret["comment"] = "Configuration will be updated"
        return ret

    res = salt_more.call_error_safe(__salt__["{:s}".format(name)], *args, **kwargs)
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to update configuration: {:}".format(res["error"])
        return ret

    ret["result"] = True
    ret["comment"] = "Sucessfully updated configuration"
    ret["changes"]["old"] = old
    ret["changes"]["new"] = new

    return ret

