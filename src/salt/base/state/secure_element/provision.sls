{%- if salt["pillar.get"]("minion:secure_element") in ["nxp05x", "softhsm"] %}
secure-element-provisioned:
  secure_element.provisioned
{%- endif %}