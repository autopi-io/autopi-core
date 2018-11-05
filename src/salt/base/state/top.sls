
base:
  '*':
    - requirements
    - raspi.config
    - minion.config
{%- if salt["pillar.get"]("setup:mpcie:module", default="ec2x") == "ec2x" %}
    - network.wwan.qmi.install
{%- else %}
    - network.wwan.qmi.uninstall
{%- endif %}
    - network.wlan
    - audio.config
    - redis.server
{%- if salt["pillar.get"]("setup:mpcie:module", default="ec2x") in ["ec2x", "bg96"] %}
    - ec2x.config
{%- endif %}
    - ui
    - power.spm.install  # Highest risk last
