
le910cx-assert-lsusb-test:
  cmd.run:
    - name: "lsusb | grep Telit"

le910cx-assert-modem-tty-usb-test:
  cmd.run:
    - name: "ls /dev/ | grep -e \"ttyUSB0\" && ls /dev/ | grep -e \"ttyUSB1\" && ls /dev/ | grep -e \"ttyUSB2\""

le910cx-assert-modem-ttytlt-usb-test:
  cmd.run:
    - name: "ls /dev/ | grep -e \"ttyTLT00\" && ls /dev/ | grep -e \"ttyTLT01\" && ls /dev/ | grep -e \"ttyTLT02\""

le910cx-sim-card-present-test:
  cmd.run:
    - name: "qmicli --device-open-qmi --device /dev/cdc-wdm0 --uim-get-card-status | grep -q \"Card state: 'present'\""

le910cx-qmi-test:
  module.run:
    - name: qmi.system_info

