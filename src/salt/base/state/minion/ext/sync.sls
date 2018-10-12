
{%- set _custom_modules = salt['pillar.get']('minion_ext:custom_modules', default=[]) %}

{%- if _custom_modules %}

minion-refresh-modules-after-synced:
  module.wait:
    - name: saltutil.refresh_modules

{%- for module in _custom_modules %}
{%- if module.get('enabled', False) %}
minion-custom-{{ module['type'] }}-{{ module['name'] }}-synced:
  file.managed:
    - name: /opt/autopi/salt/{{ module['type'] }}s/{{ module['name'] }}.py
    - source: {{ salt['pillar.get']('cloud_api:url')|replace("https://", "https+token://{:s}@".format(salt['pillar.get']('cloud_api:token'))) }}/dongle/modules/{{ module['id'] }}?format=file
    - source_hash: {{ module['hash'] }}
    - makedirs: true
    - watch_in:
      - module: minion-refresh-modules-after-synced
{%- else %}
minion-custom-{{ module['type'] }}-{{ module['name'] }}-removed:
  file.absent:
    - name: /opt/autopi/salt/{{ module['type'] }}s/{{ module['name'] }}.py
minion-custom-{{ module['type'] }}-{{ module['name'] }}-binary-removed:
  file.absent:
    - name: /opt/autopi/salt/{{ module['type'] }}s/{{ module['name'] }}.pyc
    - require:
      - file: minion-custom-{{ module['type'] }}-{{ module['name'] }}-removed
    - watch_in:
      - module: minion-refresh-modules-after-synced
{%- endif %}
{%- endfor %}

{%- endif %}
