
include:
  {%- if salt["pillar.get"]("power:firmware:version")|float < 3.0 %}
  - power.stn.config
  {%- else %}
  - power.spm.config
  {%- endif %}