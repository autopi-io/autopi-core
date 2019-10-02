
{%- if salt['pillar.get']('state', default='REGISTERED') == 'REGISTERED' %}
ensure-default-wlan-networks-removed:
  file.replace:
    - name: /etc/salt/grains
    - pattern: "^  - priority: [0-9]+\n    psk: [^\n\r]+\n    ssid: AutoPi QC[^\n\r]*\n"
    - repl: ""

refresh-grains-after-ensure-default-wlan-networks-removed:
  module.run:
    - name: saltutil.refresh_grains
    - onchanges:
      - file: /etc/salt/grains
{%- endif %}

wpa-supplicant-configured:
  file.managed:
    - name: /etc/wpa_supplicant/wpa_supplicant.conf
    - source: salt://network/wlan/client/wpa_supplicant.conf.jinja
    - template: jinja

wpa-manager-service-configured:
  file.managed:
    - name: /lib/systemd/system/wpa-manager.service
    - source: salt://network/wlan/client/wpa-manager.service

wpa-manager-service-running:
  service.running:
    - name: wpa-manager
    - enable: true
    - require:
      - file: /lib/systemd/system/wpa-manager.service
    - watch:
      - file: /lib/systemd/system/wpa-manager.service
      - file: /etc/wpa_supplicant/wpa_supplicant.conf