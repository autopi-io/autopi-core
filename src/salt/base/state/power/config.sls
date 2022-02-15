include:
  {%- if salt["pillar.get"]("power:firmware:version")|float < 3.0 %}
  - power.stn.config
  {%- else %}
  - power.spm.config
  {%- endif %}

# Required to signal that SLS 'power.config' has run
power-config:
  test.succeed_without_changes:
    - require:
      {%- if salt["pillar.get"]("power:firmware:version")|float < 3.0 %}
      - sls: power.stn.config
      {%- else %}
      - sls: power.spm.config
      {%- endif %}