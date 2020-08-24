
sleep-timer-configured:
  {%- if salt['pillar.get']('power:sleep_timer') %}
  file.serialize:
    - name: /opt/autopi/power/sleep_timer.yml
    - dataset_pillar: power:sleep_timer
    - formatter: yaml
    - show_changes: True
    - watch_in:
      - module: sleep-timers-refreshed-after-configure
  {%- else %}
  file.absent:
    - name: /opt/autopi/power/sleep_timer.yml
  {%- endif %}

sleep-timers-refreshed-after-configure:
  module.wait:
    - name: power.sleep_timer
    - refresh: *
