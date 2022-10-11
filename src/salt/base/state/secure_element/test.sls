
# TODO: Only applicable for hwversions 6.1+

crypto-i2c-present-test:
  cmd.run:
    {%- if salt["pillar.get"]("minion:hw.version", salt['config.get']('hw.version')) in [6.2, 6.3] %}
    - name: "i2cdetect -y 1 | grep '40:.*48'"
    {%- else %}
    - name: "i2cdetect -y 1 | grep '60:.*60'"
    {%- endif %}

crypto-module-communicates:
  test.module:
    - name: crypto.query
    - args:
      - serial_number
    - validate:
      - isinstance(ret["value"], str)
    - require:
      - crypto-i2c-present-test

