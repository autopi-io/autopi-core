{%- if salt["pillar.get"]("minion:hw.version") > 6.1 %}
secure-element-provisioned:
  secure_element.provisioned
{%- endif %}