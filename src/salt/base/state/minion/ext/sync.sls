{%- set _custom_modules = salt['pillar.get']('minion_ext:custom_modules', default=[]) %}
{%- if _custom_modules %}

{%- set _all_requirements = [] %}
{%- for module in _custom_modules %}
{%- if module.get('enabled', False) %}

minion-custom-{{ module['type'] }}-{{ module['name'] }}-synced:
  file.managed:
    - name: /opt/autopi/salt/{{ module['type'] }}s/{{ module['name'] }}.py
    - source: {{ salt['pillar.get']('cloud_api:url')|replace("https://", "https+token://{:s}@".format(salt['pillar.get']('cloud_api:auth_token'))) }}/dongle/modules/{{ module['id'] }}?format=file
    - source_hash: {{ module['hash'] }}
    - makedirs: true
    - watch_in:
      {%- if module['type'] in ['engine'] %}
      - module: minion-restart-after-ext-synced
      {%- else %}
      - module: minion-refresh-modules-after-ext-synced
      {%- endif %}

  {%- for requirement in module.get('requirements', []) if not requirement in _all_requirements %}
    {%- do _all_requirements.append(requirement) %}
  {%- endfor %}

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
      {%- if module['type'] in ['engine'] %}
      - module: minion-restart-after-ext-synced
      {%- else %}
      - module: minion-refresh-modules-after-ext-synced
      {%- endif %}

{%- endif %}
{%- endfor %}

{%- if _all_requirements %}

minion-custom-requirements-file-distributed:
  file.managed:
    - name: /opt/autopi/salt/requirements.txt
    - source: salt://minion/ext/requirements.txt.jinja
    - template: jinja
    - context:
        lines: {{ _all_requirements|tojson }}

minion-custom-requirements-installed:
  pip.installed:
    - requirements: /opt/autopi/salt/requirements.txt
    - upgrade: true  # Needed in order to get newest changes from git repos
    - require:
      - file: /opt/autopi/salt/requirements.txt
    - unless: diff /opt/autopi/salt/requirements.txt /opt/autopi/salt/requirements-installed.txt

minion-custom-requirements-installation-completed:
  file.managed:
    - name: /opt/autopi/salt/requirements-installed.txt
    - source: /opt/autopi/salt/requirements.txt
    - watch:
      - pip: minion-custom-requirements-installed
    - watch_in:
      - module: minion-restart-after-ext-synced

{%- else %}

minion-custom-requirements-file-removed:
  file.absent:
    - name: /opt/autopi/salt/requirements.txt

{%- endif %}

minion-restart-after-ext-synced:
  module.wait:
    - name: minionutil.request_restart
    - reason: minion_ext_synced

minion-refresh-modules-after-ext-synced:
  module.wait:
    - name: saltutil.refresh_modules

{%- endif %}
