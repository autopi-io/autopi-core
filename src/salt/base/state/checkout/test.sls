audio-test:
  module.run:
    - name: audio.play
    - audio_file: /usr/share/sounds/alsa/Front_Center.wav

modem-device-found:
  cmd.run:
    - name: "lsusb | grep -q \"2c7c:0121\""

assert-modem-ttyusb:
  cmd.run:
    - name: "ls /dev/ | grep -e \"ttyUSB0\" && ls /dev/ | grep -e \"ttyUSB1\" && ls /dev/ | grep -e \"ttyUSB2\" && ls /dev/ | grep -e \"ttyUSB3\""

sim-card-present:
  cmd.run:
    - name: "qmicli --device-open-qmi --device /dev/cdc-wdm0 --uim-get-card-status | grep -q \"Card state: 'present'\""

modem-test:
  module.run:
    - name: ec2x.product_info

qmi-test:
  module.run:
    - name: qmi.system_info

spm-test:
  module.run:
    - name: spm.query
    - cmd: version

obd-test:
  module.run:
    - name: obd.query
    - cmd: rpm
    - force: true

acc-test:
  module.run:
    - name: acc.query
    - cmd: xyz

rpi-test:
  module.run:
    - name: rpi.temp

stn-test:
  module.run:
    - name: stn.power_config

power-test:
  module.run:
    - name: power.status
