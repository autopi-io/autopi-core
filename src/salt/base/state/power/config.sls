
avrdude-configured:
  file.managed:
    - name: /etc/avrdude.conf
    - source: salt://power/avrdude.conf

uart-wake-trigger:
  stn.power_trigger:
    - name: uart_wake
    - enable: True
    - rule: "0-30000 us"

uart-sleep-trigger:
  stn.power_trigger:
    - name: uart_sleep
    - enable: True
    - rule: "600 s"  # 10 min

voltage-level-wake-trigger:
  stn.power_trigger:
    - name: volt_level_wake
    - enable: False  # Not used
    - rule: ">13.20V FOR 1 s"

voltage-change-wake-trigger:
  stn.power_trigger:
    - name: volt_change_wake
    - enable: True
    - rule: "+0.20V IN 1000 ms"

voltage-level-sleep-trigger:
  stn.power_trigger:
    - name: volt_level_sleep
    - enable: True
    - rule: "<12.20V FOR 300 s"  # 5 min

{%- if salt["pillar.get"]("spm:auto_update", False) %}
spm-release-distributed:
  file.managed:
    - name: /opt/autopi/power/spm-{{ salt["pillar.get"]("spm:version") }}.hex
    - source: salt://power/spm-{{ salt["pillar.get"]("spm:version") }}.hex
    - makedirs: True

spm-release-installed:
  spm.firmware_flashed:
    - name: /opt/autopi/power/spm-{{ salt["pillar.get"]("spm:version") }}.hex
    - version: {{ salt["pillar.get"]("spm:version") }}
{%- endif %}
