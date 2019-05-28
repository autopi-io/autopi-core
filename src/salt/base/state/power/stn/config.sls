
# We need to be able to wake up STN through UART when waking up by timer
uart-wake-trigger:
  stn.power_trigger:
    - name: uart_wake
    - enable: True
    - rule: "0-30000 us"

# Power off STN upon UART inactivity (prevents permanent sleep where RPi is off and STN is on)
uart-sleep-trigger:
  stn.power_trigger:
    - name: uart_sleep
    - enable: True
    - rule: "900 s"  # 15 min

voltage-level-wake-trigger:
  stn.power_trigger:
    - name: volt_level_wake
    {%- if salt['pillar.get']('power:wake_trigger:voltage_level', default='') %}
    - enable: True
    {%- else %}
    - enable: False
    {%- endif %}
    - rule: "{{ salt['pillar.get']('power:wake_trigger:voltage_level', default='>13.20') }}V FOR {{ salt['pillar.get']('power:wake_trigger:voltage_level_duration', default='1') }} s"

# Wake upon engine started (battery charging)
voltage-change-wake-trigger:
  stn.power_trigger:
    - name: volt_change_wake
    - enable: True
    - rule: "{{ salt['pillar.get']('power:wake_trigger:voltage_change', default='+0.20') }}V IN {{ salt['pillar.get']('power:wake_trigger:voltage_change_duration', default='1000') }} ms"

# Power off on low battery
voltage-level-sleep-trigger:
  stn.power_trigger:
    - name: volt_level_sleep
    - enable: True
    - rule: "<{{ salt['pillar.get']('power:safety_cut-out:voltage', default='12.20') }}V FOR {{ salt['pillar.get']('power:safety_cut-out:duration', default='300') }} s"
