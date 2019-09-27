
wlan-network-removed:
  file.replace:
    - name: /etc/salt/grains
    - pattern: "^  - priority: 1\n    psk: .+\n    ssid: AutoPi .+\n$"
    - repl: ""

refresh-grains-after-wlan-network-removed:
  module.run:
    - name: saltutil.refresh_grains
    - onchanges:
      - file: /etc/salt/grains