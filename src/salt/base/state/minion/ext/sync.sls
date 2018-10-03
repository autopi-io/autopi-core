
{%- set _custom_modules = salt['pillar.get']('minion_ext:custom_modules', default=[]) %}

{%- if _custom_modules %}
minion-custom-modules-synced:
{%- for module in _custom_modules %}
  {%- if module.get('enabled', False) %}
  file.managed:
    - name: /opt/autopi/salt/{{ module['type'] }}s/{{ module['name'] }}.py
    - source: {{ salt['pillar.get']('cloud_api:url')|replace("https://", "https+token://{:s}@".format(salt['pillar.get']('cloud_api:token'))) }}/dongle/modules/{{ module['id'] }}?format=file
    - source_hash: {{ module['hash'] }}
    - makedirs: true
  {%- else %}
  file.absent:
    - name: /opt/autopi/salt/{{ module['type'] }}s/{{ module['name'] }}.py
  {%- endif %}
{%- endfor %}

# TODO: Reload modules?

{%- endif %}
