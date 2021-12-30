
# Delete unused packages exclusive configuration files
unused-pkgs-removed:
  pkg.removed:
    - pkgs:
      - raspberrypi-net-mods

avahi-daemon-disabled:
  service.disabled:
    - name: avahi-daemon
avahi-daemon-masked:
  service.masked:
    - name: avahi-daemon

raspi-config-disabled:
  service.disabled:
    - name: raspi-config
raspi-config-masked:
  service.masked:
    - name: raspi-config

alsa-restore-disabled:
  service.disabled:
    - name: alsa-restore
alsa-restore-masked:
  service.masked:
    - name: alsa-restore

ipv6-disabled:
  file.replace:
    - name: /etc/modprobe.d/ipv6.conf
    - pattern: "^#?options ipv6 disable_ipv6=.*$"
    - repl: "options ipv6 disable_ipv6=1"
    - append_if_not_found: true
    - ignore_if_missing: true

ipv6-driver-blacklisted:
  file.replace:
    - name: /etc/modprobe.d/ipv6.conf
    - pattern: "^#?blacklist ipv6$"
    - repl: "blacklist ipv6"
    - append_if_not_found: true
    - ignore_if_missing: true
    
ipv6-rules-deleted:
  file.absent:
    - name: /etc/iptables/rules.v6  # Must be deleted to prevent boot error when ipv6 is diabled
