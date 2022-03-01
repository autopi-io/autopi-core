
{%- if salt['pillar.get']('power:volt_factor', 0.0) %}
spm-voltage-factor-configured:
  module_extra.configured:
    - name: spm.query
    - args:
        - volt_factor
    - kwargs:
        value: {{ salt['pillar.get']('power:volt_factor', 0.0) }}
{%- endif %}

# Wake upon engine started (battery charging)
spm-voltage-change-wake-trigger-configured:
  module_extra.configured:
    - name: spm.query
    - args:
        - wake_volt_change
    - kwargs:
        difference: {{ salt['pillar.get']('power:wake_trigger:voltage_change', default='0.50') }}
        period: {{ salt['pillar.get']('power:wake_trigger:voltage_change_duration', default=1000) }}

# Wake when engine is running (battery charging)
spm-voltage-level-wake-trigger-configured:
  module_extra.configured:
    - name: spm.query
    - args:
        - wake_volt_level
    - kwargs:
        threshold: {{ salt['pillar.get']('power:wake_trigger:voltage_level', default='13.20').replace('>', '') }}
        duration: {{ salt['pillar.get']('power:wake_trigger:voltage_level_duration', default=3) * 1000 }}

# Power off on low battery
spm-voltage-level-sleep-trigger-configured:
  module_extra.configured:
    - name: spm.query
    - args:
        - hibernate_volt_level
    - kwargs:
        threshold: {{ salt['pillar.get']('power:safety_cut-out:voltage', default='12.20') }}
        duration: {{ salt['pillar.get']('power:safety_cut-out:duration', default=240) * 1000 }}
