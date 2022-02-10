rfid-settings-configured:
  file.serialize:
    - name: /opt/autopi/rfid/settings.yaml
    - makedirs: true
    - dataset_pillar: rfid
    - formatter: yaml
    - show_changes: True

rfid-settings-loaded:
  module.run:
    - name: rfid.load_settings
    - require:
      - file: rfid-settings-configured
    - onchanges:
      - file: /opt/autopi/rfid/settings.yaml