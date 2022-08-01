
include:
  - raspi.boot

autopi-qc-wifi-network-configured:
    grains.present:
        - name: wpa_supplicant:networks
        - force: true
        - value:
            - priority: 1
              psk: autopi2018
              ssid: AutoPi QC

autopi-qc-wifi-network-wpa-supplicant-configured:
    file.managed:
        - name: /etc/wpa_supplicant/wpa_supplicant.conf
        - source: salt://network/wlan/client/wpa_supplicant.conf.jinja
        - template: jinja
        - require:
            - grains: autopi-qc-wifi-network-configured