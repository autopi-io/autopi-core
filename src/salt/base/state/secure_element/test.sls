
# TODO: Only applicable for hwversions 6.1+

crypto-i2c-present-test:
  cmd.run:
    - name: "i2cdetect -y 1 | grep '40:.*48'"

crypto-module-communicates:
  test.module:
    - name: crypto.query
    - args:
      - serial_number
    - validate:
      - isinstance(ret["value"], str)
    - require:
      - crypto-i2c-present-test

