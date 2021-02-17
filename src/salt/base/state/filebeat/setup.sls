
include:
  {%- if salt["pillar.get"]("filebeat") %}
  - .install
  - .config
  {%- else %}
  - .uninstall
  {%- endif %}

# Required to signal that SLS 'filebeat.setup' has run
filebeat-setup:
  test.succeed_without_changes:
    - require:
      {%- if salt["pillar.get"]("filebeat") %}
      - sls: .install
      - sls: .config
      {%- else %}
      - sls: .uninstall
      {%- endif %}