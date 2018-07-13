
include:
  - hostapd
  - dnsmasq

dhcpcd-static-ip-config:
  file.managed:
    - name: /etc/dhcpcd.conf
    - source: salt://network/wlan/hotspot/dhcpcd.conf.jinja
    - template: jinja

dhcpcd-service-running:
  service.running:
    - name: dhcpcd
    - watch:
      - file: /etc/dhcpcd.conf

dhcpcd-fast-boot-enabled:
  file.absent:
    - name: /etc/systemd/system/dhcpcd.service.d/wait.conf

ip-forward-enabled:
  file.replace:
    - name: /etc/sysctl.conf
    - pattern: "^#?net.ipv4.ip_forward=.*$"
    - repl: net.ipv4.ip_forward=1

# Just activate IP forward immediately instead of waiting until next reboot
ip-forward-activated:
  cmd.run:
    - name: "echo 1 > /proc/sys/net/ipv4/ip_forward"
    - onchanges:
      - file: ip-forward-enabled

iptables-persistent-installed:
  pkg.installed:
    - name: iptables-persistent

iptables-ipv4-rules-config:
  file.managed:
    - name: /etc/iptables/rules.v4
    - source: salt://network/wlan/hotspot/iptables-ipv4.rules
    - require:
      - pkg: iptables-persistent

# Load rules immediately instead of waiting until next reboot
iptables-ipv4-rules-loaded:
  cmd.run:
    - name: "iptables-restore < /etc/iptables/rules.v4"
    - onchanges:
      - file: iptables-ipv4-rules-config
