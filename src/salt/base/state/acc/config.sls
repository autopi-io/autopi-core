
standby-mode-before-changes:
  module_extra.configured:
    - name: acc.active
    - kwargs:
        enable: false
    - prereq:
      - module_extra: wake-interrrupt-pin-configured
      - module_extra: wake-interrrupt-enabled
      - module_extra: wake-on-motion-enabled

wake-interrrupt-pin-configured:
  module_extra.configured:
    - name: acc.intr_pin
    - args:
        - wake
    - kwargs:
        value: int1  # TODO: Change to int2 when done testing

wake-interrrupt-enabled:
  module_extra.configured:
    - name: acc.intr
    - args:
        - wake
    - kwargs:
        enable: true

wake-on-motion-enabled:
  module_extra.configured:
    - name: acc.wake
    - args:
        - motion
    - kwargs:
        enable: true

activated:
  module_extra.configured:
    - name: acc.active
    - kwargs:
        enable: true