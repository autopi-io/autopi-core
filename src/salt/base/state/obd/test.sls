
# NOTE: Only applicable to socketcan devices (hwversion 6.0+)

obd-loggers-killed-requisite:
  module.run:
    - name: obd.manage
    - args:
      - worker
      - kill
      - "*"

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
    - require:
      - obd-loggers-killed-requisite

can0-iface-init-test:
  cmd.run:
    - name: "dmesg | grep 'can0.*successfully initialized'"
    - require:
      - obd-loggers-killed-requisite

can1-iface-init-test:
  cmd.run:
    - name: "dmesg | grep 'can1.*successfully initialized'"
    - require:
      - obd-loggers-killed-requisite

can0-iface-setup-test:
  cmd.run:
    - name: "ip link set can0 down && ip link set can0 up type can bitrate 500000"
    - require:
      - obd-loggers-killed-requisite

can1-iface-setup-test:
  cmd.run:
    - name: "ip link set can1 down && ip link set can1 up type can bitrate 500000"
    - require:
      - obd-loggers-killed-requisite

can1-iface-dump-test:
  cmd.run:
    - name: "candump -T 3000 -n 1 can1 > /tmp/can1.dump"
    - bg: True  # Run this as a background task in order to move forward with the rest of the tests
    - require:
      - obd-loggers-killed-requisite

can0-iface-send-test:
  cmd.run:
    - name: "cansend can0 7DF#020707"
    - require:
      - can-term-setup-test
      - obd-loggers-killed-requisite

can1-iface-recv-test:
  cmd.run:
    - name: "grep \"can1  7DF   \\[3\\]  02 07 07\" /tmp/can1.dump"
    - require:
      - can1-iface-dump-test
      - can0-iface-send-test
      - obd-loggers-killed-requisite
