
# TODO: Make this configurable from the advanced settings
le910cx-fw-switch-configured:
  module.run:
    - name: modem.connection
    - cmd: active_firmware_image
    - kwargs:
        net_conf: global
