
{%- set bin_file_path = "/opt/autopi/ble/dtm-" ~ salt["pillar.get"]("ble:firmware:version", default="3.2.1") ~ ".bin" %} 

ble-firmware-distributed:
  file.managed:
    - name: {{ bin_file_path }}.orig
    - source: salt://ble/dtm-{{ salt["pillar.get"]("ble:firmware:version", default="3.2.1") }}.bin
    - source_hash: salt://ble/dtm-{{ salt["pillar.get"]("ble:firmware:version", default="3.2.1") }}.bin.sha1
    - makedirs: true

ble-requirement-bbe-installed:
  pkg.installed:
    - name: bbe

ble-firmware-local-name-imprinted:
  cmd.run:
    - name: "bbe -e 's/_LOCAL_NAME_/{{ grains["id"][-12:] }}/' {{ bin_file_path }}.orig -o {{ bin_file_path }} && (diff <(xxd {{ bin_file_path }}.orig) <(xxd {{ bin_file_path }}); test $? -eq 1)"
    - shell: /bin/bash
    - require:
      - file: ble-firmware-distributed
      - pkg: bbe

# Only flash BLE chip during device checkout
{%- if salt["pillar.get"]("state", default="REGISTERED") == "NEW" %}
ble-firmware-flashed:
  module.run:
    - name: ble.flash_firmware
    - bin_file: {{ bin_file_path }}
    - check_only: false
    - confirm: true
{%- endif %}

ble-mac-address-queried:
  module.run:
    - name: ble.interface
    - args:
      - mac_address
    - returner: cloud.returner
