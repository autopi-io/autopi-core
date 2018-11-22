import copy
import logging
import salt.loader

from messaging import EventDrivenMessageProcessor, keyword_resolve


log = logging.getLogger(__name__)

# Message processor
edmp = EventDrivenMessageProcessor("reactor")

returners = None

context = {}


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
def returner_handler(name, event, mutate_group=None):
    """
    Call a Salt returner module.
    """

    ctx = context.setdefault("returner", {}).setdefault(name, {})

    if mutate_group != None:

        # Find last event for mutate group
        last_event = ctx.get(mutate_group, None)

        # Compare current event with last to determine if it has mutated
        if last_event == None or last_event["tag"] != event["tag"] or \
            {k: v for k, v in event["data"] if not k.startswith("_")} != \
                {k: v for k, v in last_event["data"] if not k.startswith("_")}:

            returners[name](event)

        # Always store latest event in context
        ctx[mutate_group] = event

    else:

        returners[name](event)


@edmp.register_hook()
def context_handler(key=None, **kwargs):
    """
    """

    if key != None:
        if not key in context:
            context[key] = {}

        for k, v in kwargs.iteritems():
            context[key][k.replace("__", ".")] = v

    return context


@edmp.register_hook()
def echo_handler(event):
    """
    For testing.
    """

    log.info("Echo: {:}".format(event))


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

                # Check condition if defined
                condition = mapping.get("condition", None)
                if condition:
                    if keyword_resolve(condition, keywords={"event": event, "match": match, "context": context}):
                        log.info("Event meets condition '{:}': {:}".format(condition, event))
                    else:
                        return

                # Process all action messages
                for message in mapping["actions"]:

                    # Check if keyword resolving is enabled
                    if mapping.get("keyword_resolve", False):
                        resolved_message = keyword_resolve(copy.deepcopy(message), keywords={"event": event, "match": match, "context": context})
                        log.debug("Keyword resolved message: {:}".format(resolved_message))

                        edmp.process(resolved_message)
                    else:
                        edmp.process(message)

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

