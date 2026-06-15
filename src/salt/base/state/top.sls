
base:
  '*':
    - requirements  # Most important
    - raspi.install
    - minion.install
    {%- if salt["pillar.get"]("setup:mpcie:module", default="ec2x") in ["ec2x", "le910cx", "bg96"] %}
    - network.wwan.qmi.install
    {%- else %}
    - network.wwan.qmi.uninstall
    {%- endif %}
    {%- if salt["pillar.get"]("minion:hw.version", salt["config.get"]("hw.version")) >= 7.0 %}
    - network.eth.config
    {%- endif %}
    - network.wlan.client.config
    - network.wlan.hotspot.install
    - network.firewall.config
    {%- if salt["pillar.get"]("minion:hw.version", salt["config.get"]("hw.version")) < 6.0 %}
    - obd.install
    {%- else %}
    - can.utils.install
    - can.socketcand.setup
    {%- endif %}
    - audio.install
    - redis.server
    - mosquitto
    {%- if salt["pillar.get"]("docker:enabled", default=False) %}
    - docker.install
    {%- else %}
    - docker.uninstall
    {%- endif %}
    {%- if salt["pillar.get"]("setup:mpcie:module", default="ec2x") in ["ec2x", "bg96"] %}
    - ec2x.config
    {%- elif salt["pillar.get"]("setup:mpcie:module", default="ec2x") == "le910cx" %}
    - le910cx.config
    {%- endif %}
    {%- if salt["pillar.get"]("ble:enabled", default=False) %}
    - ble.install
    {%- endif %}
    - ui.install
    - power.sleep_timer.config
    - power.spm.install
    - power.config
    - minion.certs
    {%- if salt['grains.get']('osmajorrelease') < 11 %}
    - secure_element.install
    {%- endif %}
    - logrotate.config
