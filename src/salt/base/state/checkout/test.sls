
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
    - validate: ret["value"] in ["1.1.1.0", "2.0", "2.1"]

obd-test:
  test.module:
    - name: obd.query
    - args:
      - elm_voltage
    - kwargs:
        protocol: None
    - validate: ret["value"] > 12.0

acc-test:
  test.module:
    - name: acc.query
    - args:
      - xyz
    - validate:
      - round(ret["x"], 1) == 0.0
      - round(ret["y"], 1) == 0.0
      - round(ret["z"], 1) == 1.0

acc-interrupt-timeout-check:
  test.module:
    - name: acc.context
    - validate:
      - ret["interrupt"]["timeout"] <= 2
      - ret["interrupt"]["total"] > 0

rpi-test:
  test.module:
    - name: rpi.temp
    - validate:
      - ret["cpu"]["value"] > 30.0
      - ret["gpu"]["value"] > 30.0

stn-test:
  test.module:
    - name: stn.power_config
    - validate: ret["ctrl_mode"] == "NATIVE"

power-test:
  test.module:
    - name: power.status
    - validate: '"rpi" in ret'
    - validate: '"spm" in ret'
    - validate: '"stn" in ret'

rtc-test:
  cmd.run:
    - name: "hwclock -r"
