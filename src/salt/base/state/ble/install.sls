
{%- set bin_file_path = "/opt/autopi/ble/dtm-" ~ salt["pillar.get"]("ble:firmware:version") ~ ".bin" %} 

ble-firmware-distributed:
  file.managed:
    - name: {{ bin_file_path }}.orig
    - source: salt://ble/dtm-{{ salt["pillar.get"]("ble:firmware:version") }}.bin
    - source_hash: salt://ble/dtm-{{ salt["pillar.get"]("ble:firmware:version") }}.bin.sha1
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

# TODO HN: Only run if 'ble.interface version' is different
ble-firmware-installed:
  module.run:
    - name: ble.flash_firmware
    - bin_file: {{ bin_file_path }}
    - check_only: false
    - confirm: true

ble-mac-address-queried:
  module.run:
    - name: ble.interface
    - args:
      - mac_address
    - returner: cloud.returner
