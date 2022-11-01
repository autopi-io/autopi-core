
eth0-advertise-configured:
  file.replace:
    - name: /etc/network/if-pre-up.d/ethtool
    - pattern: "^#?\\$ETHTOOL --change eth0 advertise .*$"
    - repl: "$ETHTOOL --change eth0 advertise 0x00F"
    - append_if_not_found: true