
include:
  {%- if salt["pillar.get"]("ble") %}
  - .install
  {%- else %}
  - .uninstall
  {%- endif %}

# Required to signal that SLS 'ble.setup' has run
ble-setup:
  test.succeed_without_changes:
    - require:
      {%- if salt["pillar.get"]("ble") %}
      - sls: ble.install
      {%- else %}
      - sls: ble.uninstall
      {%- endif %}