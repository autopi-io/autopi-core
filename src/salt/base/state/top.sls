
base:
  '*':
    - requirements
    - raspi.config
    - minion.config
    - cloud.config
    - network.wwan.qmi
    - network.wlan
    - audio.config
    - redis.server
    {%- if salt["pillar.get"]("setup:mpcie:module", default="ec2x") == "ec2x" %}
    - ec2x.config
    {%- endif %}
    - ui
    - power.spm.install  # Highest risk last
