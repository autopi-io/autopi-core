
standby-mode-before-changes:
  module_extra.configured:
    - name: acc.query
    - args:
      - active
    - kwargs:
        enable: false
    - prereq:
      - module_extra: wake-interrrupt-pin-configured
      - module_extra: wake-interrrupt-enabled
      - module_extra: wake-on-motion-enabled

wake-interrrupt-pin-configured:
  module_extra.configured:
    - name: acc.query
    - args:
        - intr_pin
        - wake
    - kwargs:
        value: int1  # TODO: Change to int2 when done testing

wake-interrrupt-enabled:
  module_extra.configured:
    - name: acc.query
    - args:
        - intr
        - wake
    - kwargs:
        enable: true

wake-on-motion-enabled:
  module_extra.configured:
    - name: acc.query
    - args:
        - wake
        - motion
    - kwargs:
        enable: true

activated:
  module_extra.configured:
    - name: acc.query
    - args:
        - active
    - kwargs:
        enable: true