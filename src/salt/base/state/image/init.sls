
include:
  - raspi.boot
  - raspi.config
  - network.firewall.config

exclude:
  - id: hciuart
  - id: iptables-ipv4-rules-loaded
  - id: timezone-configured
  - id: i2c-module-reloaded
  - id: rc-local-configured # Disabel this to prevent the build process from removing the existing content in the rc.local which is doing the filesystem expand after it has been shrinked...

{%- if salt['pillar.get']('image:clear-wifi') %}

autopi-wifi-network-configured:
    grains.present:
        - name: wpa_supplicant:networks
        - force: true
        - value: []

{%- else %}

autopi-wifi-network-configured:
    grains.present:
        - name: wpa_supplicant:networks
        - force: true
        - value:
            - priority: 1
              psk: autopi2018
              ssid: AutoPi QC

{%- endif %}

autopi-qc-wifi-network-wpa-supplicant-configured:
    file.managed:
        - name: /etc/wpa_supplicant/wpa_supplicant.conf
        - source: salt://network/wlan/client/wpa_supplicant.conf.jinja
        - template: jinja
        - require:
            - grains: autopi-wifi-network-configured