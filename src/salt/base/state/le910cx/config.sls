
# TODO: Make this configurable from the advanced settings
le910cx-fw-switch-configured:
  module.run:
    - name: modem.connection
    - cmd: active_firmware_image
    - kwargs:
        net_conf: global

le910cx-evmoni-disabled-for-config:
  module.run:
    - name: modem.connection
    - cmd: evmoni_enabled
    - kwargs:
        enabled: False
        confirm: True

le910cx-evmoni-configured:
  module.run:
    - name: modem.connection
    - cmd: evmoni_config
    - kwargs:
        instance: 3
        urcmod: 1
        timeout: 5
        confirm: True
    - require:
      - module: le910cx-evmoni-disabled-for-config

le910cx-evmoni-smsin-configured:
  module.run:
    - name: modem.connection
    - cmd: evmoni_smsin_config
    - kwargs:
        enabled: True
        command: "AT#GPIO=3,1,1"
        match_content: ""
        confirm: True
        force: False
    - require:
      - module: le910cx-evmoni-disabled-for-config

le910cx-evmoni-gpio-configured:
  module.run:
    - name: modem.connection
    - cmd: evmoni_gpio_config
    - args:
      - 1
    - kwargs:
        enabled: True
        command: "AT#GPIO=3,0,1"
        gpio_pin: 3
        watch_status: True
        confirm: True
        delay: 5
    - require:
      - module: le910cx-evmoni-disabled-for-config

le910cx-evmoni-enabled:
  module.run:
    - name: modem.connection
    - cmd: evmoni_enabled
    - kwargs:
        enabled: True
        confirm: True
    - require:
      - module: le910cx-evmoni-configured
      - module: le910cx-evmoni-smsin-configured
      - module: le910cx-evmoni-gpio-configured
        