
audio-test:
  module.run:
    - name: audio.play
    - audio_file: /opt/autopi/audio/sound/coin.wav

# Test modem as default unless none is specified in pillar
{%- if salt['pillar.get']('setup:mpcie:module', 'ec2x') %}

assert-modem-tty-usb-test:
  cmd.run:
    - name: "ls /dev/ | grep -e \"ttyUSB0\" && ls /dev/ | grep -e \"ttyUSB1\" && ls /dev/ | grep -e \"ttyUSB2\" && ls /dev/ | grep -e \"ttyUSB3\""

# Only required when testing HW
{%- if not salt['pillar.get']('setup:mpcie:module', '') %}
sim-card-present-test:
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

spm-version-test:
  test.module:
    - name: spm.query
    - args:
      - version
    {%- if salt['config.get']('spm.version', 2.2) < 3.0 %}
    - validate: ret["value"] in ["1.1.1.0", "2.0", "2.1", "2.2"]
    {%- else %}
    - validate: ret["value"] in ["3.1"]
    {%- endif %}

acc-xyz-test:
  test.module:
    - name: acc.query
    - args:
      - xyz
    - validate:
      {%- if salt['pillar.get']('state', '') %}
      - abs(ret["x"] - -1.0) < 0.1
      - abs(ret["y"] - 0.0) < 0.1
      - abs(ret["z"] - 0.0) < 0.1
      {%- else %}
      - abs(ret["x"] - 0.0) < 0.1
      - abs(ret["y"] - 0.0) < 0.1
      - abs(ret["z"] - -1.0) < 0.1
      {%- endif %}

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
    - validate: abs(ret["value"] - 12.80) <= 0.1

spm-volt-config-flags-test:
  test.module:
    - name: spm.query
    - args:
      - volt_config_flags
    - validate:
      - not ret["unsaved"]["limit"]
      - not ret["unsaved"]["factor"]
      - not ret["unsaved"]["ewma_alpha"]
      - not ret["unsaved"]["hibernate_level"]
      - not ret["unsaved"]["wake_change"]
      - not ret["unsaved"]["wake_level"]
    - require:
      - spm-version-test

rtc-i2c-present-test:
  cmd.run:
    - name: "i2cdetect -y 1 0x51 0x51 | grep UU"

crypto-i2c-present-test:
  cmd.run:
    - name: "i2cget -y 1 0x60 0x00 | grep 0x04"

can-term-setup-test:
  test.module:
    - name: spm.query
    - args:
      - usr_pins
    - kwargs:
        high: can0_term,can1_term
    - validate:
      - ret["output"]["can0_term"]
      - ret["output"]["can1_term"]

can0-iface-init-test:
  cmd.run:
    - name: "dmesg | grep 'can0.*successfully initialized'"

can1-iface-init-test:
  cmd.run:
    - name: "dmesg | grep 'can1.*successfully initialized'"

can0-iface-setup-test:
  cmd.run:
    - name: "ip link set can0 down && ip link set can0 up type can bitrate 500000"

can1-iface-setup-test:
  cmd.run:
    - name: "ip link set can1 down && ip link set can1 up type can bitrate 500000"

can1-iface-dump-test:
  cmd.run:
    - name: "candump -T 3000 -n 1 can1 > /tmp/can1.dump"
    - bg: True  # Run this as a background task in order to move forward with the rest of the tests

can0-iface-send-test:
  cmd.run:
    - name: "cansend can0 7DF#020707"
    - require:
      - can-term-setup-test

can1-iface-recv-test:
  cmd.run:
    - name: "grep \"can1  7DF   \\[3\\]  02 07 07\" /tmp/can1.dump"
    - require:
      - can1-iface-dump-test
      - can0-iface-send-test

{%- endif %}

rtc-device-present-test:
  cmd.run:
    - name: "ls -la /dev/rtc"

rtc-dmesg-not-missing-test:
  cmd.run:
    - name: "dmesg | grep -c \"RTC chip is not present\" | grep 0"  # We expect to NOT have that line in dmesg

rtc-systohc-and-get-time-test:
  cmd.run:
    - name: "hwclock -w && hwclock -r"
