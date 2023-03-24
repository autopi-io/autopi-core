Changelog

## Unreleased
+ Added ability for obd.play to play both 11 and 29 bit messages from the same dump file.

- Fixed obd.dump putting hashes in the wrong places when recording messages that don't match selected protocol. (Previously would cause 'fromhex' error on obd.play)
- Fixed issue where selecting adaptive timing causes indentation error
- Fixed command 'minionutil.change_master' to only perform changes directly in the minion config file.

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
