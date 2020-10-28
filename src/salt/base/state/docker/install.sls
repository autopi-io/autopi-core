# Install balena-engine
sound-folder-created:
  file.directory:
    - name: /opt/autopi/docker
    - makedirs: true

balena-engine-install-script-present:
  file.managed:
    - name: /opt/autopi/docker/balena-engine-install.sh
    - source: salt://docker/balena-engine-install.sh
    - mode: 755
    - user: root
    - group: root

balena-engine-installed:
  cmd.run:
   - name: /opt/autopi/docker/balena-engine-install.sh

# use script instead to make sure correct version is retrieved arm6 and arm7 for rpi4
# balena-engine-installed:
#   cmd.run:
#     - name: curl -sL "https://github.com/balena-os/balena-engine/releases/download/v17.12.0/balena-engine-v17.12.0-armv7.tar.gz" | sudo tar xzv -C /usr/local/bin --strip-components=1

## Doesnt work, will cause causes 
# docker-python-wrapper-installed: 
#   pip.installed:
#    - name: docker == 4.3.1

# Fixes
backports-ssl-match-hostname-removed:
  pip.removed:
   - name: backports.ssl-match-hostname

ssl-match-hostname-installed:
  pkg.installed:
    - name: python-backports.ssl-match-hostname

# Services
balena-engine-service-configured:
  file.managed:
    - name: /lib/systemd/system/balena-engine.service
    - source: salt://docker/balena-engine.service

balena-engine-socket-configured:
  file.managed:
    - name: /lib/systemd/system/balena-engine.socket
    - source: salt://docker/balena-engine.socket

# Group
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