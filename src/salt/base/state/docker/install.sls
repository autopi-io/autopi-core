{% set _version = salt["pillar.get"]("balena:version", "v20.10.43") -%} 

balena-engine-installed:
  cmd.script:
    - name: salt://docker/balena-engine-install.sh
    - env:
      - tag: {{ _version }}
    - unless: "cat /usr/local/bin/balena-engine-version.txt | grep {{ _version }}"

# Fix
backports-ssl-match-hostname-removed:
  pip.removed:
   - name: backports.ssl-match-hostname

{%- if salt['grains.get']('osmajorrelease') == 10 %}
ssl-match-hostname-installed:
  pkg.installed:
    - name: python-backports.ssl-match-hostname
{%- endif %}

balena-engine-service-configured:
  file.managed:
    - name: /lib/systemd/system/balena-engine.service
    - source: salt://docker/balena-engine.service

balena-engine-socket-configured:
  file.managed:
    - name: /lib/systemd/system/balena-engine.socket
    - source: salt://docker/balena-engine.socket

balena-engine-group-present:
  group.present:
    - name: balena-engine
    - system: True

balena-engine-restart-service:
  cmd.run:
    - name: systemctl restart balena-engine.service

balena-engine-service-running:
  service.running:
    - name: balena-engine
    - enable: true
    - require:
      - file: /lib/systemd/system/balena-engine.service
      - group: balena-engine
    - watch:
      - file: /lib/systemd/system/balena-engine.service