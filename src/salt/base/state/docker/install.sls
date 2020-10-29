
{% set _version = salt["pillar.get"]("balena:version", "v17.12.0") -%} 

balena-engine-installed:
  cmd.script:
    - name: salt://docker/balena-engine-install.sh
    - env:
      - tag: {{ _version }}
    - unless: "balena-engine version | grep {{ _version }}"

# Fix
backports-ssl-match-hostname-removed:
  pip.removed:
   - name: backports.ssl-match-hostname
ssl-match-hostname-installed:
  pkg.installed:
    - name: python-backports.ssl-match-hostname

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

balena-engine-service-running:
  service.running:
    - name: balena-engine
    - enable: true
    - require:
      - file: /lib/systemd/system/balena-engine.service
      - group: balena-engine
    - watch:
      - file: /lib/systemd/system/balena-engine.service