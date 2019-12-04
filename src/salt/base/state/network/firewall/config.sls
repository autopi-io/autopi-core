
iptables-persistent-installed:
  pkg.installed:
    - name: iptables-persistent

iptables-ipv4-rules-config:
  file.managed:
    - name: /etc/iptables/rules.v4
    - source: salt://network/firewall/iptables-ipv4.rules.jinja
    - template: jinja
    - require:
      - pkg: iptables-persistent

# Load rules immediately instead of waiting until next reboot
iptables-ipv4-rules-loaded:
  cmd.run:
    - name: "iptables-restore < /etc/iptables/rules.v4"
    - onchanges:
      - file: iptables-ipv4-rules-config
