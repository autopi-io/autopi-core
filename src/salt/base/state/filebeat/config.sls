
filebeat-configured:
  file.serialize:
    - name: /etc/filebeat/filebeat.yml
    - dataset_pillar: filebeat
    - formatter: yaml
    - show_changes: True

filebeat-service-running:
  service.running:
    - name: filebeat
    - watch:
      - file: /etc/filebeat/filebeat.yml

filebeat-scrubber-service-configured:
  file.managed:
    - name: /lib/systemd/system/filebeat-scrubber.service
    - source: salt://filebeat/scrubber.service.jinja
    - template: jinja

filebeat-scrubber-service-running:
  service.running:
    - name: filebeat-scrubber
    - watch:
      - file: /lib/systemd/system/filebeat-scrubber.service