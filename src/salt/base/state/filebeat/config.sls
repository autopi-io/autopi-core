
{%- if salt["pillar.get"]("filebeat") %}
filebeat-configured:
  file.serialize:
    - name: /etc/filebeat/filebeat.yml
    - dataset_pillar: filebeat
    - formatter: yaml
    - show_changes: True

filebeat-service-running:
  service.running:
    - name: filebeat
    - enable: true
    - watch:
      - file: /etc/filebeat/filebeat.yml
{%- else %}
filebeat-service-disabled:
  service.dead:
    - name: filebeat
    - enable: false
{%- endif %}

{%- if salt["pillar.get"]("filebeat_scrubber") %}
filebeat-scrubber-service-configured:
  file.managed:
    - name: /lib/systemd/system/filebeat-scrubber.service
    - source: salt://filebeat/scrubber.service.jinja
    - template: jinja

filebeat-scrubber-service-running:
  service.running:
    - name: filebeat-scrubber
    - enable: true
    - watch:
      - file: /lib/systemd/system/filebeat-scrubber.service
{%- else %}
filebeat-scrubber-service-disabled:
  service.dead:
    - name: filebeat-scrubber
    - enable: false
{%- endif %}