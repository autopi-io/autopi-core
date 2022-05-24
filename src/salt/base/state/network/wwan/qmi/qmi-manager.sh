#!/bin/bash
# ATTENTION: This file is managed by AutoPi and any manual changes may be overwritten during update!


# Constants
###############################################################################

readonly SCRIPT=$(readlink -f "$0")
readonly CONF=/etc/qmi-manager.conf

# Exit codes
readonly OK=0
readonly ERROR=1
readonly ERROR_FATAL=10


# Configuration variables
###############################################################################

VERBOSE=false
RUN_INTERVAL_ONLINE=300 # 5 mins
RUN_INTERVAL_OFFLINE=30 # 30 secs
MAX_RETRY=3
AUTO_REBOOT=false
MODE=qmi
PING_HOST=google.com
SIM_CONF=/etc/qmi-sim.conf


# Helper functions
###############################################################################

print_usage ()
{
    echo "Usage: $0 [COMMAND]"
}

print_help ()
{
    echo "Usage: $0 [COMMAND]"
    echo
    echo "Network connection management of QMI device"
    echo
    echo "Commands:"
    echo "  help              Show help"
    echo "  version           Show version"
    echo "  status            Check status of QMI network connection"
    echo "  up                Bring up QMI network connection manually"
    echo "  down              Take down QMI network connection manually"
    echo "  run               Ensure QMI network connection is always up"
    echo
}

print_version ()
{
    echo "$0 0.0"
    echo
}

echoerr ()
{
    echo "$@" 1>&2
}

retry ()
{
    local max=$1
    local delay=$2
    local cmd=$3

    for i in $(seq 0 $max); do
        if [ $i -gt 0 ]; then
            [ $VERBOSE == true ] && echo "[INFO] Attempting retry $i/$max in $delay second(s)..."
            sleep $delay
        fi

        eval $cmd
        local retcode=$?

        [ $retcode -eq 0 ] && break
        echoerr "[WARN] Command failed with exit code $retcode: $cmd"
    done

    return $retcode
}

online_callback ()
{
    # Call online callback command if defined
    [ $VERBOSE == true ] && [ ! -z ${ONLINE_CALLBACK+x} ] && echo "[INFO] Executing online callback command: $ONLINE_CALLBACK"
    [ ! -z ${ONLINE_CALLBACK+x} ] && eval $ONLINE_CALLBACK 1>/dev/null && [ $? -gt 0 ] && echoerr "[ERROR] Failed to execute online callback command"
}

offline_callback ()
{
    # Call offline callback command if defined
    [ $VERBOSE == true ] && [ ! -z ${OFFLINE_CALLBACK+x} ] && echo "[INFO] Executing offline callback command: $OFFLINE_CALLBACK"
    [ ! -z ${OFFLINE_CALLBACK+x} ] && REASON=$(printf "$1" | tail -1 | sed -e "s/^\[ERROR\] //") && eval $OFFLINE_CALLBACK 1>/dev/null && [ $? -gt 0 ] && echoerr "[ERROR] Failed to execute offline callback command"
}

status ()
{
    [ $VERBOSE == true ] && echo "[INFO] Checking status of QMI device '$DEVICE'..."

    # Check/wait for the device to be present
    retry 5 1 "test -c $DEVICE"
    [ $? -gt 0 ] && echoerr "[ERROR] QMI device not found '$DEVICE'" && return $ERROR_FATAL
    [ $VERBOSE == true ] && echo "[INFO] QMI device present '$DEVICE'"

    # Check QMI network connection status
    qmicli --device-open-$MODE --device $DEVICE --wds-get-packet-service-status | grep -q "Connection status: 'connected'"
    [ $? -gt 0 ] && echoerr "[ERROR] QMI network not connected" && return $ERROR
    [ $VERBOSE == true ] && echo "[INFO] QMI network connected"

    # Check for assigned IP address
    local ip=$(ip addr show $INTERFACE | grep -oP "inet \K\S[0-9.]+")
    [ $? -gt 0 ] && echoerr "[ERROR] Interface '$INTERFACE' has no IP" && return $ERROR
    [ $VERBOSE == true ] && echo "[INFO] Interface '$INTERFACE' has IP '$ip'"

    # Perform ping test
    ping -q -I $INTERFACE -c3 $PING_HOST &>/dev/null
    [ $? -gt 0 ] && echoerr "[ERROR] Unable to ping '$PING_HOST' using interface '$INTERFACE'" && gather_info && return $ERROR
    [ $VERBOSE == true ] && echo "[INFO] Able to ping '$PING_HOST' with interface '$INTERFACE'"

    # Check if uDHCP client is running
    pkill -0 -F /var/run/udhcpc.$INTERFACE.pid
    [ $? -gt 0 ] && echoerr "[ERROR] No uDHCP client process running for interface '$INTERFACE'" && return $ERROR
    [ $VERBOSE == true ] && echo "[INFO] uDHCP client running for interface '$INTERFACE'"

    return $OK
}

gather_info()
{
    qmicli --device-open-$MODE --device $DEVICE --nas-get-signal-strength
    sleep .5

    # qmicli --device-open-$MODE --device $DEVICE --nas-get-system-info
    # sleep .5

    # qmicli --device-open-$MODE --device $DEVICE --nas-get-home-network
    # sleep .5

    qmicli --device-open-$MODE --device $DEVICE --nas-get-serving-system
    sleep .5

    # qmicli --device-open-$MODE --device $DEVICE --nas-get-operator-name
    # sleep .5

    qmicli --device-open-$MODE --device $DEVICE --nas-get-system-selection-preference
    sleep .5

    autopi ec2x.query "AT+COPS?"
    autopi ec2x.query "AT+CREG?;+CEREG?;+CGREG?"
}

up ()
{
    [ $VERBOSE == true ] && echo "[INFO] Bringing up connection for QMI device '$DEVICE'..."

    # Check/wait for the device to be present
    retry 5 1 "test -c $DEVICE"
    [ $? -gt 0 ] && echoerr "[ERROR] QMI device not found '$DEVICE'" && return $ERROR_FATAL
    [ $VERBOSE == true ] && echo "[INFO] QMI device present '$DEVICE'"

    # Check if we can communicate with the device by querying model information
    STDERR=$(qmicli --device-open-$MODE --device $DEVICE --dms-get-model 3>&1 1>&2 2>&3 | tee >(cat 1>&2); exit ${PIPESTATUS[0]})
    [ $? -gt 0 ] && echoerr "[ERROR] Failed to communicate with QMI device -" $(printf "$STDERR" | grep "^error:") && return $ERROR
    [ $VERBOSE == true ] && echo "[INFO] Successfully communicated with QMI device"

    # Check if SIM card is present
    retry 3 1 "qmicli --device-open-$MODE --device $DEVICE --uim-get-card-status | grep -q \"Card state: 'present'\""
    [ $? -gt 0 ] && echoerr "[ERROR] No SIM card present" && return $ERROR
    [ $VERBOSE == true ] && echo "[INFO] SIM card is present"

    # Look for SIM config file
    if [ -e $SIM_CONF ]; then
        echo "Going into SIM configuration flow"

        # Load SIM config file
        source $SIM_CONF
        [ $VERBOSE == true ] && echo "[INFO] Loaded SIM config file at '$SIM_CONF'"

        # Try to unlock SIM
        unlock_sim
        [ $? -gt 0 ] && return $ERROR

    else
        echoerr "[WARN] No SIM config file found at '$SIM_CONF'"
    fi

    # Ensure QMI device is in online operating mode
    qmicli --device-open-$MODE --device $DEVICE --dms-get-operating-mode | grep -q "Mode: 'online'"
    if [ $? -gt 0 ]; then
        echo "Going to put device in operating mode online..."

        qmicli --device-open-$MODE --device $DEVICE --dms-set-operating-mode=online
        [ $? -gt 0 ] && echoerr "[ERROR] Failed to put QMI device into online operating mode" && return $ERROR
        [ $VERBOSE == true ] && echo "[INFO] QMI device is put into online operating mode"

        # Give device some time to be ready before network check and start of connection
        # NOTE: Too little time results in errors and establish of connection fails
        sleep 1
    else
        [ $VERBOSE == true ] && echo "[INFO] QMI device is already in online operating mode"
    fi

    # Check for network
    retry 3 1 "qmicli --device-open-$MODE --device $DEVICE --nas-get-home-network | grep -q \"Home network:\""
    [ $? -gt 0 ] && echoerr "[ERROR] No mobile network found" && gather_info && return $ERROR
    [ $VERBOSE == true ] && echo "[INFO] Mobile network present"

    # Check if SIM is registered
    retry 3 1 "qmicli --device-open-$MODE --device $DEVICE --nas-get-serving-system | grep -q \"Registration state: 'registered'\""
    [ $? -gt 0 ] && echoerr "[ERROR] SIM not registered" && gather_info && return $ERROR
    [ $VERBOSE == true ] && echo "[INFO] SIM is registered"

    # Start QMI network connection
    STDERR=$(qmi-network $DEVICE start 3>&1 1>&2 2>&3 | tee >(cat 1>&2); exit ${PIPESTATUS[0]})
    [ $? -gt 0 ] && echoerr "[ERROR] Failed to start QMI network connection -" $(printf "$STDERR" | grep "^error:\|^call end reason") && gather_info && return $ERROR
    [ $VERBOSE == true ] && echo "[INFO] Started QMI network connection"

    # Ensure uDHCP client not already running
    [ -f /var/run/udhcpc.$INTERFACE.pid ] && pkill -0 -F /var/run/udhcpc.$INTERFACE.pid
    [ $? -eq 0 ] && echoerr "[ERROR] uDHCP client process already running for interface '$INTERFACE'" && return $ERROR

    # Start uDHCP client
    if [ "$1" == "run" ]; then
        udhcpc -S -R -b -p /var/run/udhcpc.$INTERFACE.pid -i $INTERFACE -t 5 -s /etc/udhcpc/qmi.script 3>&1  # Fixes problem where this methods hangs when called from 'run' function
    else
        udhcpc -S -R -b -p /var/run/udhcpc.$INTERFACE.pid -i $INTERFACE -t 5 -s /etc/udhcpc/qmi.script
    fi
    [ $? -gt 0 ] && echoerr "[ERROR] Failed to start uDHCP client for interface '$INTERFACE'" && return $ERROR
    [ $VERBOSE == true ] && echo "[INFO] Started uDHCP client for interface '$INTERFACE'"

    return $OK
}

down ()
{
    local retcode=$OK

    [ $VERBOSE == true ] && echo "[INFO] Taking down connection for QMI device '$DEVICE'..."

    # Stop QMI network connection
    qmi-network $DEVICE stop
    if [ $? -gt 0 ]; then
        echoerr "[ERROR] Failed to stop QMI network"
        retcode=$ERROR
    elif [ $VERBOSE == true ]; then
        echo "[INFO] Stopped QMI network"
    fi

    # Put QMI device into low power operating mode if enabled
    if [ $POWER_SAVE == true ]; then
        echo "Entering power save mode"

        # Will do IMSI detach and RF off, and if the module resets the setting is re-applied (i.e. it doesn't go to online automatically)
        qmicli --device-open-$MODE --device $DEVICE --dms-set-operating-mode=persistent-low-power
        if [ $? -gt 0 ]; then
            echoerr "[ERROR] Failed to put QMI device into low power operating mode"
            retcode=$ERROR
        elif [ $VERBOSE == true ]; then
            echo "[INFO] QMI device is put into low power operating mode"
        fi
    fi

    # Stop uDHCP client
    [ -f /var/run/udhcpc.$INTERFACE.pid ] && pkill -F /var/run/udhcpc.$INTERFACE.pid
    if [ $? -eq 0 ] && [ $VERBOSE == true ]; then
        echo "[INFO] Stopped uDHCP client for interface '$INTERFACE'"
    fi

    return $retcode
}

unlock_sim ()
{
    # First check if SIM card is PIN protected
    qmicli --device-open-$MODE --device $DEVICE --uim-get-card-status | grep -q "PIN1 state: 'disabled'"
    if [ $? == 0 ]; then
        [ $VERBOSE == true ] && echo "[INFO] SIM card not PIN protected"
        return $OK
    fi

    # Then check if SIM card is already unlocked
    qmicli --device-open-$MODE --device $DEVICE --uim-get-card-status | grep -q "PIN1 state: 'enabled-verified'"
    if [ $? == 0 ]; then
        [ $VERBOSE == true ] && echo "[INFO] SIM card already unlocked"
        return $OK
    fi

    # Check if a PIN code is defined
    [ -z $PIN ] && echoerr "[ERROR] No valid PIN found in '$SIM_CONF'" && return $ERROR

    # Unlock SIM card using PIN from config file
    qmicli --device-open-$MODE --device $DEVICE --uim-verify-pin=PIN1,$PIN
    [ $? -gt 0 ] && echoerr "[ERROR] Failed to unlock SIM card using PIN defined in '$SIM_CONF'" && return $ERROR
    [ $VERBOSE == true ] && echo "[INFO] Unlocked SIM card using PIN defined in '$SIM_CONF'"

    # Give modem a little time to get ready after unlock
    sleep 1

    return $OK
}

run ()
{
    # Is SIM present
    retry 3 1 "qmicli --device-open-$MODE --device $DEVICE --uim-get-card-status | grep -q \"Card state: 'present'\""
    [ $? -gt 0 ] && echoerr "[ERROR] No SIM card present" && return $ERROR
    [ $VERBOSE == true ] && echo "[INFO] SIM card is present"

    # Is network selection preference set to automatic?
    retry 3 1 "qmicli --device-open-$MODE --device $DEVICE --nas-get-system-selection-preference | grep -q \"Network selection preference: 'automatic'\""
    if [ $? -gt 0 ]; then
        echoerr "[ERROR] Network selection preference is not 'automatic', going to manually set that"
        echo "[INFO] Network selection preference is not 'automatic', going to manually set that"

        # Set it to the correct value before beginning connection procedure
        autopi ec2x.query "AT+COPS=0"
        [ $? -gt 0 ] && echoerr "[ERROR] Failed to set operator selection to automatic" && gather_info && return $ERROR
        [ $VERBOSE == true ] && echo "[INFO] Successfully set operator selection to automatic"

        # Remove me later
        echo "[INFO] Successfully set operator selection to automatic"
    else
        echo "[INFO] Network selection preference is already set to 'automatic'"
    fi

    local has_been_up=false
    local interval=0
    local retry=0

    [ $VERBOSE == true ] && echo "[INFO] Running QMI manager..."

    while true; do

        # Check if max retry attempts have been exceeded
        if [ $retry -ge $MAX_RETRY ]; then
            echoerr "[WARN] Reached max retry attempt ($retry/$MAX_RETRY) to get connection online"

            [ $AUTO_REBOOT == true ] && echoerr "[WARN] Rebooting..." && reboot
            exit $ERROR
        fi

        # Check current connection status
        STDERR=$(status 3>&1 1>&2 2>&3 | tee >(cat 1>&2); exit ${PIPESTATUS[0]})
        local retcode=$?
        if [ $retcode -eq $OK ]; then
            [ $VERBOSE == true ] && echo "[INFO] Connection is already online"

            has_been_up=true
            online_callback

            retry=0
            interval=$RUN_INTERVAL_ONLINE
        elif [ $retcode -eq $ERROR_FATAL ]; then
            echoerr "[WARN] Fatal error occurred"

            offline_callback "$STDERR"

            [ $AUTO_REBOOT == true ] && echoerr "[WARN] Rebooting..." && reboot

            exit $ERROR_FATAL
        else
            echoerr "[WARN] Connection is offline"

            retry=$((retry + 1))
            interval=$RUN_INTERVAL_OFFLINE

            if [ $has_been_up == true ]; then
                echo "Bringing connection down"
                # Ensure connection is down
                has_been_up=false
                down
            fi

            # Try to bring up connection
            STDERR=$(up "run" 3>&1 1>&2 2>&3 | tee >(cat 1>&2); exit ${PIPESTATUS[0]})
            if [ $? -eq $OK ]; then
                echo "Connection up, will save it to variable"
                has_been_up=true

                # Check status to confirm connection is actually up
                STDERR=$(status 3>&1 1>&2 2>&3 | tee >(cat 1>&2); exit ${PIPESTATUS[0]})
                if [ $? -eq $OK ]; then
                    [ $VERBOSE == true ] && echo "[INFO] Connection is now online"

                    online_callback
                else
                    offline_callback "$STDERR"
                fi
            else
                offline_callback "$STDERR"
            fi
        fi

        [ $VERBOSE == true ] && echo "[INFO] Sleeping $interval secs..."
        sleep $interval
    done
}


# Main flow
###############################################################################

# Validate arguments
if [ $# -lt 1 ]; then
    echoerr "[ERROR] Invalid argument(s)"
    print_usage
    exit 255
fi

# Load config file if exists
[ ! -e $CONF ] && echoerr "[ERROR] No config file found at '$CONF'" && exit $ERROR
source $CONF
[ $VERBOSE == true ] && echo "[INFO] Loaded config file at '$CONF'"

# Validate config params
[ -z $DEVICE ] && echoerr "[ERROR] No 'DEVICE' found in '$CONF'" && exit $ERROR
[ -z $INTERFACE ] && echoerr "[ERROR] No 'INTERFACE' found in '$CONF'" && exit $ERROR
[ -z $PING_HOST ] && echoerr "[ERROR] No 'PING_HOST' found in '$CONF'" && exit $ERROR

# Process commands
case $1 in
    "help")
        print_help
        ;;
    "version")
        print_version
        ;;
    "run")
        run
        ;;
    "status")
        status
        [ $? -eq $OK ] && echo "Connection online"
        ;;
    "up")
        up
        [ $? -eq $OK ] && echo "Connection up"
        ;;
    "down")
        down
        [ $? -eq $OK ] && echo "Connection down"
        ;;
    *)
        echoerr "[ERROR] Unsupported command '$1'"
        print_help
        exit 255
        ;;
esac
exit $?
