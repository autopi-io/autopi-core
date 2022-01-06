
audio-test:
  module.run:
    - name: audio.play
    - audio_file: /opt/autopi/audio/sound/coin.wav

# Test modem as default unless none is specified in pillar
{%- if salt['pillar.get']('setup:mpcie:module', 'ec2x') %}

assert-modem-ttyusb:
  cmd.run:
    - name: "ls /dev/ | grep -e \"ttyUSB0\" && ls /dev/ | grep -e \"ttyUSB1\" && ls /dev/ | grep -e \"ttyUSB2\" && ls /dev/ | grep -e \"ttyUSB3\""

# Only required when testing HW
{%- if not salt['pillar.get']('setup:mpcie:module', '') %}
sim-card-present:
  cmd.run:
    - name: "qmicli --device-open-qmi --device /dev/cdc-wdm0 --uim-get-card-status | grep -q \"Card state: 'present'\""
{%- endif %}

modem-test:
  test.module:
    - name: ec2x.product_info
    - validate: '"Quectel" in ret["data"]'

qmi-test:
  module.run:
    - name: qmi.system_info

{%- endif %}

spm-test:
  test.module:
    - name: spm.query
    - args:
      - version
    {%- if salt['config.get']('spm.version', 2.2) < 3.0 %}
    - validate: ret["value"] in ["1.1.1.0", "2.0", "2.1", "2.2"]
    {%- else %}
    - validate: ret["value"] in ["3.0"]
    {%- endif %}

acc-xyz-test:
  test.module:
    - name: acc.query
    - args:
      - xyz
    - validate:
      - abs(ret["x"] - -1.0) < 0.1
      - abs(ret["y"] - 0.0) < 0.1
      - abs(ret["z"] - 0.0) < 0.1

acc-interrupt-timeout-check:
  test.module:
    - name: acc.manage
    - args:
      - context
    - validate:
      - ret["interrupt"]["timeout"] <= 2
      - ret["interrupt"]["total"] > 0

rpi-temp-test:
  test.module:
    - name: rpi.temp
    - validate:
      - ret["cpu"]["value"] > 30.0
      - ret["gpu"]["value"] > 30.0

{%- if salt['config.get']('spm.version', 2.2) < 3.0 %}

obd-test:
  test.module:
    - name: obd.query
    - args:
      - elm_voltage
    - kwargs:
        protocol: None
    - validate: ret["value"] > 12.0

stn-test:
  test.module:
    - name: stn.power_config
    - validate: ret["ctrl_mode"] == "NATIVE"

power-status-test:
  test.module:
    - name: power.status
    - validate:
      - '"rpi" in ret'
      - '"spm" in ret'
      - '"stn" in ret'

rtc-i2c-present-test:
  cmd.run:
    - name: "i2cdetect -y 1 0x68 0x68 | grep UU"

{%- else %}

power-status-test:
  test.module:
    - name: power.status
    - validate:
      - '"rpi" in ret'
      - '"spm" in ret'
      - ret["spm"]["last_state"]["up"] == "on"
      - ret["spm"]["last_trigger"]["up"] == "plug"

spm-volt-readout-test:
  test.module:
    - name: spm.query
    - args:
      - volt_readout
    - validate: abs(ret["current"] - 12.80) <= 0.1

spm-volt-trigger-flags-test:
  test.module:
    - name: spm.query
    - args:
      - volt_trigger_flags
    - validate:
      - not ret["unsaved"]["hibernate_level"]
      - not ret["unsaved"]["wake_change"]
      - not ret["unsaved"]["wake_level"]

rtc-i2c-present-test:
  cmd.run:
    - name: "i2cdetect -y 1 0x51 0x51 | grep UU"

rtc-linux-device-present-test:
  cmd.run:
    - name: "ls -la /dev/rtc"

# we expect to NOT have that line in dmesg
rtc-dmesg-does-not-report-missing-chip-test:
  cmd.run:
    - name: "dmesg | grep -c \"RTC chip is not present\" | grep 0"

crypto-i2c-present-test:
  cmd.run:
    - name: "i2cget -y 1 0x60 0x00 | grep 0x04"

ensure-can-termination-test:
  test.module:
    - name: spm.query
    - args:
      - usr_pins
    - kwargs:
        high: can0_term,can1_term
    - validate:
      - ret["output"]["can0_term"]
      - ret["output"]["can1_term"]

force-setup-can0-interface-test:
  cmd.run:
    - name: "ip link set can0 down && ip link set can0 up type can bitrate 500000"

force-setup-can1-interface-test:
  cmd.run:
    - name: "ip link set can1 down && ip link set can1 up type can bitrate 500000"

# TODO: cmd.run|shell: 'candump -T 3 can1' in a named screen session
# TODO: cmd.run|shell: 'cansend can0 7DF#02010C'
# TODO: cmd.run|shell: Reattch to aboce screen session and assert that messages was received

{%- endif %}

# Not required when testing HW because the command fails before RTC time has been set the first time (from NTP server)
{%- if salt['pillar.get']('state', '') %}
rtc-read-time-test:
  cmd.run:
    - name: "hwclock -r"
{%- endif %}