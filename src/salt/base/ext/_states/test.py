import logging
import salt_more


log = logging.getLogger(__name__)


def module(name, args=[], kwargs={}, validate=[]):
    """
    Tests a module.
    """

    ret = {
        "name": name,
        "result": None,
        "changes": {},
        "comment": ""
    }

    res = salt_more.call_error_safe(__salt__["{:s}".format(name)], *args, **kwargs)
    if "error" in res:
        ret["result"] = False
        ret["comment"] = "Failed to test module: {:}".format(res["error"])

        return ret

    ret["result"] = True
    ret["comment"] = "Sucessfully tested module"
    ret["changes"]["ret"] = res

    for expr in validate if isinstance(validate, list) else [validate]:
        try:
            success = eval(expr, {"ret": res})

            if not success:
                ret["result"] = False
                ret["comment"] = "Module test failed due to invalid result"

            ret["changes"].setdefault("eval", {})[expr] = success

        except Exception as ex:
            log.exception("Failed to validate result")

            ret["result"] = False
            ret["comment"] = "Module test failed due to failure in validation"
            ret["changes"].setdefault("eval", {})[expr] = str(ex)

    return ret


def succeed_without_changes(name, comment='Success!'):
    '''
    Returns successful.
    .. versionadded:: 2014.7.0
    name
        A unique string.
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': comment
    }
    return ret


def succeed_with_changes(name, comment='Success!', changes={}):
    '''
    Returns successful and changes is not empty
    .. versionadded:: 2014.7.0
    name:
        A unique string.
    '''
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': comment
    }

    # Following the docs as written here
    # http://docs.saltstack.com/ref/states/writing.html#return-data
    ret['changes'] = changes or {
        'testing': {
            'old': 'Unchanged',
            'new': 'Something pretended to change'
        }
    }

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = ('If we weren\'t testing, this would be successful '
                          'with changes')

    return ret
