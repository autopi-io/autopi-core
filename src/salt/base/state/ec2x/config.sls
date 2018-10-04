
include:
  - .gnss.config

urc-port-configured:
  module_extra.configured:
    - name: ec2x.urc_port_config
    - kwargs:
        value: {{ salt['pillar.get']('ec2x:urc_port') }}

ri-other-disabled:
  module_extra.configured:
    - name: ec2x.ri_other_config
    - kwargs:
        value: "off"

ri-signal-output-configured:
  module_extra.configured:
    - name: ec2x.ri_signal_config
    - kwargs:
        value: physical