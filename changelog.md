Changelog

## Unreleased
+ Added command can.j1939_query and support for J1939 auto-detection.
+ Added support for multi-frame J1939 query responses in BAM and P2P modes
+ Added ability for obd.play to play both 11 and 29 bit messages from the same dump file.
+ Added VIN and ODOMETER to supported commands on SocketCAN devices 
+ Added a configuration flag (allow_sending_can_frames) to disallow a CAN connection from sending messages on the bus
+ Added a configuration flag (allow_interface_changes) to disallow a CAN connection from running socketcan.XXX commands
+ Added more verbose error handling for obd.play
+ Added log rotations based on file size
+ Added passthrough interval to alternating_readout filter (currently only obd_manager)
+ Added commands to rpi module for getting system health and status
+ Added option to enable TCP MTU discovery (PLPMTUD).
+ Added extra checks on certificate type in certificate handling module, and event on failure to generate certificate

- Fixed an issue where SMS messages sent by non-numerical senders weren't getting parsed correctly and ignored.
- Fixed obd.dump putting hashes in the wrong places when recording messages that don't match selected protocol. (Previously would cause 'fromhex' error on obd.play)
- Fixed issue where selecting adaptive timing causes indentation error
- Fixed command 'minionutil.change_master' to only perform changes directly in the minion config file.
- Fixed issue where sending a non-OBD2 command would interfere with further commands on SocketCAN devices. 
- Fixed issue with protocol verification causing some can logger messages to be discarded
- Fixed issue with obd.query command not working after bus autodetect fails on startup
- Fixed an issue where under specific conditions second pdp context will not be cleared even if it's requested
- Fixed an issue with the stretch apt repo
- Fixed issues with dependency imports for certificate handling

## 1.24.5
+ Allow data returned from workflow to dictate topic name
+ fix: changed order of initialization to allow failed events to be sent from crypto_manager
+ Trigger event 'system/release/modules_synced' during update release
+ Ensure that the key used to sign web3 cert is an EC pkey
+ Ensure that web3 certificates will be automatically re-generated if they were created with the wrong private key.
+ Fixed wifi connection problem with special characters.
+ Enforce restart delay of 1 second as default for all engines
- Added a state that ensures the permission for the private key is right/readable
- Added handling of additional exceptions when handling certificate during expirery check
- Fixed issue where pending syncs and update releases in some cases could be blocked from syncing/applying

## v1.22

+ Added more options 'topic', 'qos' and 'retain' to MQTT returner.
+ Changed MQTT returner to fill in the timestamp field (_stamp) if missing.
+ Added more options ‘topic’, ‘qos’ and ‘retain’ to MQTT returner.
+ Possible to enable Bluetooth on the hardware UART (RPi default) for devices not using STN chip.
+ Support sync of grains defined in pillar data. This can be used to override local QMI settings from the cloud.
+ Support for changing the speed of the USB hub
+ Many improvements for supporting the new CM4 version
+ Changed boot config modifications to be an atomic operation
+ Added a limit to how many times an update will be attempted before suspending the attempts.
+ Changed to use aplay to play audio by default.
+ Improved qmi-manager to better handle different situations
+ Added support for schedule update on next startup
+ Disabled more unused services in raspbian
+ Added support for new board versions

- Fixed issue where modem could be in the wrong mode.
- Improved the modem configuration.
- Fixed issue where geofences would not always be loaded properly on the device.
- Fixed wrong handling of editable pip packages in the pip module
