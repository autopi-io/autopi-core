# TODO: Make this configurable from the advanced settings
le910cx-fw-switch-configured:
  module_extra.configured:
    - name: modem.connection
    - args: 
        - active_firmware_image
    - kwargs:
        net_conf: global
        storage_conf: ram

le910cx-evmoni-configured:
  module_extra.configured:
    - name: modem.connection
    - args: 
        - evmoni_config
    - kwargs:
        instance: 3
        urcmod: True
        timeout: 5
        confirm: True

le910cx-evmoni-smsin-configured:
  module_extra.configured:
    - name: modem.connection
    - args: 
        - evmoni_smsin_config
    - kwargs:
        enabled: True
        command: "AT#GPIO=3,1,1"
        match_content: ""
        confirm: True

le910cx-evmoni-gpio-configured:
  module_extra.configured:
    - name: modem.connection
    - args:
      - evmoni_gpio_config
      - 1
    - kwargs:
        enabled: True
        command: "AT#GPIO=3,0,1"
        gpio_pin: 3
        watch_status: True
        confirm: True
        delay: 5

le910cx-ensure-evmoni-enabled:
  module_extra.configured:
    - name: modem.connection
    - args:
      - evmoni_enabled
    - kwargs:
        enabled: True
        confirm: True