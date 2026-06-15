
{%- if salt["pillar.get"]("minion:hw.version", salt["config.get"]("hw.version")) >= 7.1 %}
eth0-100mbit-advertise-removed:
  file.replace:
    - name: /etc/network/if-pre-up.d/ethtool
    - pattern: "^\\$ETHTOOL --change eth0 advertise 0x00F$"
    - repl: "#$ETHTOOL --change eth0 advertise 0x00F"
    - append_if_not_found: false
{%- else %}
eth0-100mbit-advertise-configured:
  file.replace:
    - name: /etc/network/if-pre-up.d/ethtool
    - pattern: "^#?\\$ETHTOOL --change eth0 advertise .*$"
    - repl: "$ETHTOOL --change eth0 advertise 0x00F"
    - append_if_not_found: true
{%- endif %}