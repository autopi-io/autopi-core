
standby-mode-before-changes:
  module_extra.configured:
    - name: acc.active
    - kwargs:
        enabled: false
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
        enabled: true

wake-on-motion-enabled:
  module_extra.configured:
    - name: acc.wake
    - args:
        - motion
    - kwargs:
        enabled: true

activated:
  module_extra.configured:
    - name: acc.active
    - kwargs:
        enabled: true