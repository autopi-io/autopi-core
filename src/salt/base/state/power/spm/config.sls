# Wake upon engine started (battery charging)
voltage-change-wake-trigger:
  module_extra.configured:
    - name: spm.query
    - args:
        - wake_volt_change
    - kwargs:
        difference: {{ salt['pillar.get']('power:wake_trigger:voltage_change', default='+0.20') }}
        period: {{ salt['pillar.get']('power:wake_trigger:voltage_change_duration', default='1000') }}

# Wake when engine is running (battery charging)
voltage-level-wake-trigger:
  module_extra.configured:
    - name: spm.query
    - args:
        - wake_volt_level
    - kwargs:
        threshold: {{ salt['pillar.get']('power:wake_trigger:voltage_level', default='13.20').replace(">", "") }}
        duration: {{ salt['pillar.get']('power:wake_trigger:voltage_level_duration', default='1') * 1000 }}

# Power off on low battery
voltage-level-sleep-trigger:
  module_extra.configured:
    - name: spm.query
    - args:
        - hibernate_volt_level
    - kwargs:
        threshold: {{ salt['pillar.get']('power:safety_cut-out:voltage', default='12.20') }}
        duration: {{ salt['pillar.get']('power:safety_cut-out:duration', default='300') * 1000 }}
