import copy
import logging
import salt.loader

from common_util import dict_find, dict_filter
from messaging import EventDrivenMessageProcessor, keyword_resolve


log = logging.getLogger(__name__)

# Message processor
edmp = EventDrivenMessageProcessor("reactor")

returners = None

context = {
    "lookup": lambda *args, default=None: dict_find(context, *args, default=default),
    "cache": lambda *args, default=None: dict_find(context, "cache", *args, default=default)
}


@edmp.register_hook()
def module_handler(name, *args, **kwargs):
    """
    Call a Salt execution module from within minion process.
    """

    return __salt__["minionutil.run_job"](name, *args, **kwargs)


@edmp.register_hook()
def module_direct_handler(name, *args, **kwargs):
    """
    Call a Salt execution module directy from this engine process.
    """

    return __salt__[name](*args, **kwargs)


@edmp.register_hook()
def returner_handler(name, event):
    """
    Call a Salt returner module.
    """

    returners[name](event)


@edmp.register_hook()
def context_handler(key=None, **kwargs):
    """
    Query or manipulate context instance of this engine.
    """

    ret = context

    if key != None:
        ctx = context.setdefault(key, {})

        # Set new values if given
        for k, v in kwargs.iteritems():
            ctx[k.replace("__", ".")] = v

        ret = ctx

    return ret.copy()  # Prevents '_stamp' field to be added to context


@edmp.register_hook()
def echo_handler(event):
    """
    Mainly for testing.
    """

    log.info("Echo: {:}".format(event))


@edmp.register_hook()
def cache_handler(ident=None, **kwargs):
    """
    Caches data.
    """

    ctx = context.setdefault("cache", {})

    # List all cached items if not identifier is specified
    if ident == None:
        return ctx

    # Return cached entry for identifier if not data is specified
    if not kwargs:
        return ctx.get(ident, {})

    # Go ahead and update cache
    if not ident in ctx or \
        dict_filter(ctx[ident], lambda k: not k.startswith("_")) != dict_filter(kwargs, lambda k: not k.startswith("_")):
        kwargs["_count"] = 1
        ctx[ident] = kwargs
        
        # TODO HN: Change into debug statement
        log.info("Inserted '{:}' into cache: {:}".format(ident, kwargs))

        return kwargs  # Implies that cache is updated

    else:
        kwargs["_count"] = ctx[ident]["_count"] + 1
        ctx[ident] = kwargs
        
        # TODO HN: Change into debug statement
        log.info("Updated '{:}' in cache with: {:}".format(ident, kwargs))

        return {}  # Implies that identical data is already cached


def start(mappings, **kwargs):
    try:
        log.debug("Starting event reactor")

        # Prepare returners
        global returners
        returners = salt.loader.returners(__opts__, __salt__)

        # Initialize message processor
        edmp.init(__opts__)

        # Setup event matchers
        for mapping in mappings:

            # Define function to handle events when matched
            def on_event(event, match=None, mapping=mapping):

                # Check if conditions is defined
                conditions = mapping.get("conditions", [])
                if "condition" in mapping:
                    conditions.append(mapping["condition"])
                for index, condition in enumerate(conditions):
                    if keyword_resolve(condition, keywords={"event": event, "match": match, "context": context}):
                        log.info("Event meets condition #{:} '{:}': {:}".format(index, condition, event))
                    else:
                        return

                # Process all action messages
                actions = mapping.get("actions", [])
                if "action" in mapping:
                    actions.append(mapping["action"])
                for message in actions:

                    # Check if keyword resolving is enabled
                    if mapping.get("keyword_resolve", False):
                        resolved_message = keyword_resolve(copy.deepcopy(message), keywords={"event": event, "match": match, "context": context})
                        log.debug("Keyword resolved message: {:}".format(resolved_message))

                    # TODO: Figure out if we can improve performance by processing each message in a dedicated worker thread or process?

                        res = edmp.process(resolved_message)
                    else:
                        res = edmp.process(message)

                    if len(actions) > 1 and mapping.get("chain_conditionally", False) and not res:
                        # TODO HN: Convert to debug statement
                        log.info("Breaking action chain because of result: {:}".format(res))

                        break


            match_type = None
            if "regex" in mapping:
                match_type = "regex"
            elif "startswith" in mapping:
                match_type = "startswith"
            elif "endswith" in mapping:
                match_type = "endswith"
            elif "fnmatch" in mapping:
                match_type = "fnmatch"
            else:
                log.error("No valid match type found for mapping: {:}".format(mapping))

                continue  # Skip mapping

            # Register event matcher using above function
            edmp.register_event_matcher(mapping[match_type], on_event, match_type=match_type)

        # Run message processor
        edmp.run()

    except Exception:
        log.exception("Failed to start event reactor")
        raise

    finally:
        log.info("Stopping event reactor")

