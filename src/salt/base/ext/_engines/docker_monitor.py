import logging

from messaging import EventDrivenMessageProcessor
from threading_more import intercept_exit_signal
import docker
from time import time

log = logging.getLogger(__name__)

# Last known timestamp, so that we can skip events that show up again, if service is restarted, but not due to reboot or wake.
context = {
    "newest_event_timestamp": None
}

# Message processor
edmp = EventDrivenMessageProcessor("docker_monitor", context=context)

@intercept_exit_signal
def start(**settings):
    try:
        # if log.isEnabledFor(logging.DEBUG):
        log.info("Starting docker_monitor with settings: {:}".format(settings))

        # If balena-engine restarts it will break the for loop, so keep it in a while loop.
        log.info('Creating dockerclient and Attaching to docker.events')
        docker_path = __salt__["config.get"]("docker.url", 'unix://var/run/balena-engine.sock')
        client = docker.DockerClient(base_url=docker_path)
        
        since = context["newest_event_timestamp"]
        past_events_seconds = 120
        if not since:
            # Ensure that older events not caught when they occurred is still processed, else just proceed from "NOW"/Last event.
            since = int(time()) - past_events_seconds

        for event in client.events(decode=True, since=since, filters={ "type": "container", "event": ["start", "stop"] }):
            # If event is newer than newest_event_timestamp, trigger events.
            if not context["newest_event_timestamp"] or event["time"] > context["newest_event_timestamp"]:
                context["newest_event_timestamp"] = event["time"]

                try:
                    log.info('attributes raw: {}'.format(event["Actor"]["Attributes"]))
                    event_string = "system/docker/container/{:}/{:}".format(event["Actor"]["Attributes"]["name"], event["Action"])
                    data = { k: v for k, v in event["Actor"]["Attributes"].items() }
                    log.info("Triggering event: {}".format(event))
                    __salt__["minionutil.trigger_event"](
                        event_string,
                        data=data
                    )
                except Exception:
                    log.error("An error occurred while forwarding docker event: {}".format(event))
            else:
                log.warning("event['time']: {:} was less than the newest_event_timestamp {:} - Event has likely already been handled.".format(event['time'], context['newest_event_timestamp']))

    except Exception:
        log.exception("Failed to start docker monitor")

        raise
    finally:
        log.info("Stopping docker monitor")
