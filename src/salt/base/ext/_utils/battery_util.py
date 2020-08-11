from __future__ import division


DEFAULT_NOMINAL_VOLTAGE = 12
DEFAULT_CRITICAL_LIMIT = 12.3

CHARGING_STATE       = "charging"
DISCHARGING_STATE    = "discharging"
OVERCHARGING_STATE   = "overcharging"
CHARGING_SLOW_STATE  = "charging_slow"
CRITICAL_LEVEL_STATE = "critical_level"

ALL_STATES = [
    CHARGING_STATE,
    DISCHARGING_STATE,
    OVERCHARGING_STATE,
    CHARGING_SLOW_STATE,
    CRITICAL_LEVEL_STATE
]

ERROR_STATES = [
    OVERCHARGING_STATE,
    CHARGING_SLOW_STATE,
    CRITICAL_LEVEL_STATE
]


def state_for(voltage, nominal_voltage=DEFAULT_NOMINAL_VOLTAGE, critical_limit=DEFAULT_CRITICAL_LIMIT):
    if nominal_voltage != DEFAULT_NOMINAL_VOLTAGE:
        voltage = voltage * (DEFAULT_NOMINAL_VOLTAGE / nominal_voltage)

    if voltage <= critical_limit:
        return CRITICAL_LEVEL_STATE
    elif critical_limit < voltage <= 12.8:
        return DISCHARGING_STATE
    elif 12.8 < voltage <= 13.6:
        return CHARGING_SLOW_STATE
    elif 13.6 < voltage <= 14.9:
        return CHARGING_STATE
    elif voltage > 14.9:
        return OVERCHARGING_STATE
    else:
        raise ValueError("Unable to determine state for voltage")


def is_error_state(state):
    return state in ERROR_STATES


def charge_percentage_for(voltage, nominal_voltage=DEFAULT_NOMINAL_VOLTAGE):
    if nominal_voltage != DEFAULT_NOMINAL_VOLTAGE:
        voltage = voltage * (DEFAULT_NOMINAL_VOLTAGE / nominal_voltage)

    if voltage >= 12.6:
        return 100
    elif 12.6 > voltage >= 12.5:
        return 90
    elif 12.5 > voltage >= 12.4:
        return 80
    elif 12.4 > voltage >= 12.3:
        return 70
    elif 12.3 > voltage >= 12.2:
        return 60
    elif 12.2 > voltage >= 12.1:
        return 50
    # Repeated discharge to below levels will shorten battery life
    elif 12.1 > voltage >= 11.9:
        return 40
    elif 11.9 > voltage >= 11.8:
        return 30
    elif 11.8 > voltage >= 11.6:
        return 20
    # Permanent battery damage will occur below these levels
    elif 11.6 > voltage >= 11.3:
        return 10
    else:
        return 0
