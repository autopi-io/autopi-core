#!/bin/bash


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
RUN_INTERVAL_OFFLINE=60 # 1 min
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
        local ret=$?

        [ $ret -eq 0 ] && break
        echo "[WARN] Command failed with exit code $ret: $cmd"
    done

    return $ret
}

online_callback ()
{
    # Call online callback command if defined
    [ $VERBOSE == true ] && [ ! -z ${ONLINE_CALLBACK+x} ] && echo "[INFO] Executing online callback command: $ONLINE_CALLBACK"
    [ ! -z ${ONLINE_CALLBACK+x} ] && eval $ONLINE_CALLBACK 1>/dev/null && [ $? -gt 0 ] && echo "[ERROR] Failed to execute online callback command"
}

offline_callback ()
{
    # Call offline callback command if defined
    [ $VERBOSE == true ] && [ ! -z ${OFFLINE_CALLBACK+x} ] && echo "[INFO] Executing offline callback command: $OFFLINE_CALLBACK"
    [ ! -z ${OFFLINE_CALLBACK+x} ] && REASON=$(echo "$1" | tail -1 | grep -oP "^(?:\[.*\] \K)?.*") && eval $OFFLINE_CALLBACK 1>/dev/null && [ $? -gt 0 ] && echo "[ERROR] Failed to execute offline callback command"
}

status ()
{
    # Check/wait for QMI device to be present
    retry 5 1 "test -c $DEVICE"
    [ $? -gt 0 ] && echo "[ERROR] QMI device not found '$DEVICE'" && return $ERROR_FATAL
    [ $VERBOSE == true ] && echo "[INFO] QMI device present '$DEVICE'"

    # Check QMI network connection status
    qmicli --device-open-$MODE --device $DEVICE --wds-get-packet-service-status | grep -q "Connection status: 'connected'"
    [ $? -gt 0 ] && echo "[ERROR] QMI network not connected" && return $ERROR
    [ $VERBOSE == true ] && echo "[INFO] QMI network connected"

    # Check for assigned IP address
    local ip=$(ip addr show $INTERFACE | grep -oP "inet \K\S[0-9.]+")
    [ $? -gt 0 ] && echo "[ERROR] Interface '$INTERFACE' has no IP" && return $ERROR
    [ $VERBOSE == true ] && echo "[INFO] Interface '$INTERFACE' has IP '$ip'"

    # Perform ping test
    ping -q -I $INTERFACE -c3 $PING_HOST &>/dev/null
    [ $? -gt 0 ] && echo "[ERROR] Unable to ping '$PING_HOST' using interface '$INTERFACE'" && return $ERROR
    [ $VERBOSE == true ] && echo "[INFO] Able to ping '$PING_HOST' with interface '$INTERFACE'"

    # Check if uDHCP client is running
    pkill -0 -F /var/run/udhcpc.$INTERFACE.pid
    [ $? -gt 0 ] && echo "[ERROR] No uDHCP client process running for interface '$INTERFACE'" && return $ERROR
    [ $VERBOSE == true ] && echo "[INFO] uDHCP client running for interface '$INTERFACE'"

    return $OK
}

up ()
{
    # Check if SIM card is present
    retry 3 1 "qmicli --device-open-$MODE --device $DEVICE --uim-get-card-status | grep -q \"Card state: 'present'\""
    [ $? -gt 0 ] && echo "[ERROR] No SIM card present" && return $ERROR
    [ $VERBOSE == true ] && echo "[INFO] SIM card is present"

    # Look for SIM config file
    if [ -e $SIM_CONF ]; then

        # Load SIM config file
        source $SIM_CONF
        [ $VERBOSE == true ] && echo "[INFO] Loaded SIM config file at '$SIM_CONF'"

        # Try to unlock SIM
        unlock_sim
        [ $? -gt 0 ] && return $ERROR

    else
        echo "[WARN] No SIM config file found at '$SIM_CONF'"
    fi

    # Check for network
    retry 2 1 "qmicli --device-open-$MODE --device $DEVICE --nas-get-home-network | grep -q \"Home network:\""
    [ $? -gt 0 ] && echo "[ERROR] No mobile network found" && return $ERROR
    [ $VERBOSE == true ] && echo "[INFO] Mobile network present"

    # Start QMI network connection
    qmi-network $DEVICE start
    [ $? -gt 0 ] && echo "[ERROR] Failed to start QMI network connection" && return $ERROR
    [ $VERBOSE == true ] && echo "[INFO] Started QMI network connection"

    # Ensure uDHCP client not already running
    [ -f /var/run/udhcpc.$INTERFACE.pid ] && pkill -0 -F /var/run/udhcpc.$INTERFACE.pid
    [ $? -eq 0 ] && echo "[ERROR] uDHCP client process already running for interface '$INTERFACE'" && return $ERROR

    # Start uDHCP client
    udhcpc -S -R -b -p /var/run/udhcpc.$INTERFACE.pid -i $INTERFACE -t 5 -s /etc/udhcpc/qmi.script
    [ $? -gt 0 ] && echo "[ERROR] Failed to start uDHCP client for interface '$INTERFACE'" && return $ERROR
    [ $VERBOSE == true ] && echo "[INFO] Started uDHCP client for interface '$INTERFACE'"

    return $OK
}

down ()
{
    local ret=$OK

    # Stop QMI network connection
    qmi-network $DEVICE stop
    if [ $? -gt 0 ]; then
        echo "[ERROR] Failed to stop QMI network"
        ret=$ERROR
    elif [ $VERBOSE == true ]; then
        echo "[INFO] Stopped QMI network"
    fi

    # Stop uDHCP client
    [ -f /var/run/udhcpc.$INTERFACE.pid ] && pkill -F /var/run/udhcpc.$INTERFACE.pid
    if [ $? -eq 0 ] && [ $VERBOSE == true ]; then
        echo "[INFO] Stopped uDHCP client for interface '$INTERFACE'"
    fi

    return $ret
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
    [ -z $PIN ] && echo "[ERROR] No valid PIN found in '$SIM_CONF'" && return $ERROR

    # Unlock SIM card using PIN from config file
    qmicli --device-open-$MODE --device $DEVICE --uim-verify-pin=PIN1,$PIN
    [ $? -gt 0 ] && echo "[ERROR] Failed to unlock SIM card using PIN defined in '$SIM_CONF'" && return $ERROR
    [ $VERBOSE == true ] && echo "[INFO] Unlocked SIM card using PIN defined in '$SIM_CONF'"

    # Give modem a little time to get ready after unlock
    sleep 1

    return $OK
}

run ()
{
    local interval=0
    local retry=0

    while true; do

        # Check if max retry attempts have been exceeded
        if [ $retry -ge $MAX_RETRY ]; then
            echo "[WARN] Reached max retry attempt ($retry/$MAX_RETRY) to get connection online"

            [ $AUTO_REBOOT == true ] && echo "[WARN] Rebooting..." && reboot
            exit $ERROR
        fi

        # Check current connection status
        status
        OUT=$(status)  # Output must be stored in global variable otherwise we cannot get correct exit code afterwards
        local status=$?
        echo "$OUT"  # Remember to print output

        if [ $status -eq $OK ]; then
            [ $VERBOSE == true ] && echo "[INFO] Connection is already online"

            online_callback

            retry=0
            interval=$RUN_INTERVAL_ONLINE
        elif [ $status -eq $ERROR_FATAL ]; then
            echo "[WARN] Fatal error occurred"

            offline_callback "$OUT"

            [ $AUTO_REBOOT == true ] && echo "[WARN] Rebooting..." && reboot
            exit $ERROR_FATAL
        else
            echo "[WARN] Connection is offline"

            retry=$((retry + 1))
            interval=$RUN_INTERVAL_OFFLINE

            # Ensure connection is down
            down

            # Try to bring up connection
            OUT=$(up)  # Output must be stored in global variable otherwise we cannot get correct exit code afterwards
            local up=$?
            echo "$OUT"  # Remember to print output

            if [ $up -eq $OK ]; then

                # Check status to confirm connection is actually up
                OUT=$(status)  # Output must be stored in global variable otherwise we cannot get correct exit code afterwards
                local status=$?
                echo "$OUT"  # Remember to print output

                if [ $status -eq $OK ]; then
                    [ $VERBOSE == true ] && echo "[INFO] Connection is now online"

                    online_callback
                else
                    offline_callback "$OUT"
                fi
            else
                offline_callback "$OUT"
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
    echo "[ERROR] Invalid argument(s)" 1>&2
    print_usage
    exit 255
fi

# Load config file if exists
[ ! -e $CONF ] && echo "[ERROR] No config file found at '$CONF'" && exit $ERROR
source $CONF
[ $VERBOSE == true ] && echo "[INFO] Loaded config file at '$CONF'"

# Validate config params
[ -z $DEVICE ] && echo "[ERROR] No 'DEVICE' found in '$CONF'" && exit $ERROR
[ -z $INTERFACE ] && echo "[ERROR] No 'INTERFACE' found in '$CONF'" && exit $ERROR
[ -z $PING_HOST ] && echo "[ERROR] No 'PING_HOST' found in '$CONF'" && exit $ERROR

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
        echo "[ERROR] Unsupported command '$1'" 1>&2
        print_help
        exit 255
        ;;
esac
exit $?
