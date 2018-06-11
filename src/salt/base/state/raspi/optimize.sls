
# Delete unused packages including configuration files
unused-pkgs-purged:
  pkg.purged:
    - pkgs:
      - xkb-data
      - triggerhappy

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

hciuart-disabled:
  service.disabled:
    - name: hciuart
hciuart-masked:
  service.masked:
    - name: hciuart

alsa-restore-disabled:
  service.disabled:
    - name: alsa-restore
alsa-restore-masked:
  service.masked:
    - name: alsa-restore

dphys-swapfile-disabled:
  service.disabled:
    - name: dphys-swapfile
dphys-swapfile-masked:
  service.masked:
    - name: dphys-swapfile

ipv6-disabled:
  file.replace:
    - name: /etc/modprobe.d/ipv6.conf
    - pattern: "^#?options ipv6 disable_ipv6=.*$"
    - repl: "options ipv6 disable_ipv6=1"
    - append_if_not_found: true
ipv6-driver-blacklisted:
  file.replace:
    - name: /etc/modprobe.d/ipv6.conf
    - pattern: "^#?blacklist ipv6$"
    - repl: "blacklist ipv6"
    - append_if_not_found: true
ipv6-rules-deleted:
  file.absent:
    - name: /etc/iptables/rules.v6  # Must be deleted to prevent boot error when ipv6 is diabled
