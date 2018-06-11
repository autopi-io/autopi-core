
include:
  - .config

libqmi:
  pkg.installed:
    - sources:
      - libqmi: salt://network/wwan/qmi/libqmi_1.18.2-1_armhf.deb

udhcpc:
  pkg.installed

reboot-requested-after-qmi-udev-rules-changed:
  module.wait:
    - name: power.request_reboot

/etc/udev/rules.d/99-qmi.rules:
  file.managed:
    - source: salt://network/wwan/qmi/udev.rules
    - watch_in:
      - module: reboot-requested-after-qmi-udev-rules-changed

udev-service-restarted-after-qmi-rules-changed:
  service.running:
    - name: udev
    - watch:
      - file: /etc/udev/rules.d/99-qmi.rules

py-lib-installed:
  file.recurse:
    - name: /usr/local/lib/python2.7/dist-packages/qmilib/
    - source: salt://network/wwan/qmi/pylib
    - makedirs: True
    - exclude_pat: "*test.py"

qmi-network-script-installed:
  file.managed:
    - name: /usr/bin/qmi-network
    - source: salt://network/wwan/qmi/qmi-network.sh
    - mode: 755
    - user: root
    - group: root
    - require:
      - pkg: libqmi

qmi-manager-script-installed:
  file.managed:
    - name: /usr/bin/qmi-manager
    - source: salt://network/wwan/qmi/qmi-manager.sh
    - mode: 755
    - user: root
    - group: root
    - require:
      - pkg: libqmi

qmi-manager-service-configured:
  file.managed:
    - name: /lib/systemd/system/qmi-manager.service
    - source: salt://network/wwan/qmi/qmi-manager.service
    - require:
      - file: qmi-manager-script-installed

qmi-manager-service-running:
  service.running:
    - name: qmi-manager
    - enable: true
    - require:
      - file: /lib/systemd/system/qmi-manager.service
    - watch:
      - file: /lib/systemd/system/qmi-manager.service
      - file: /etc/qmi-manager.conf
