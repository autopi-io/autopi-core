
include:
  - .config
  - dnsmasq

# No hotspot on 'wlan0' interface - only on 'uap0'
# TODO: Remove again at some point
/etc/hostapd/hostapd_wlan0.conf:
  file.absent

reboot-requested-after-ap-udev-rules-changed:
  module.wait:
    - name: power.request_reboot

/etc/udev/rules.d/90-ap.rules:
  file.managed:
    - source: salt://network/wlan/hotspot/udev.rules
    - watch_in:
      - module: reboot-requested-after-ap-udev-rules-changed

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
    - source: salt://network/wlan/hotspot/iptables-ipv4.rules.jinja
    - template: jinja
    - require:
      - pkg: iptables-persistent

# Load rules immediately instead of waiting until next reboot
iptables-ipv4-rules-loaded:
  cmd.run:
    - name: "iptables-restore < /etc/iptables/rules.v4"
    - onchanges:
      - file: iptables-ipv4-rules-config
