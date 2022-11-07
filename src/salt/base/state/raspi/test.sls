
rpi-temp-test:
  test.module:
    - name: rpi.temp
    - validate:
      - ret["cpu"]["value"] > 30.0
      - ret["gpu"]["value"] > 30.0

