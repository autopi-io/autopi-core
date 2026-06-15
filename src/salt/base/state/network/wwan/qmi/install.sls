
include:
  - .config

libqmi-installed:
  pkg.installed:
    {%- if salt['grains.get']('osmajorrelease') < 10 %}
    - name: libqmi
    - sources:
      - libqmi: salt://network/wwan/qmi/libqmi_1.18.2-1_armhf.deb
    {%- else %}
    - name: libqmi-utils
    {%- endif %}

{%- if salt['grains.get']('osmajorrelease') >= 11 %}
modem-manager-service-dead:
  service.dead:
    - name: ModemManager
    - enable: false

modem-manager-service-masked:
  service.masked:
    - name: ModemManager
{%- endif %}

udhcpc:
  pkg.installed

udhcpc-script-installed:
  file.managed:
    - name: /etc/udhcpc/qmi.script
    - source: salt://network/wwan/qmi/udhcpc.script
    - mode: 755
    - user: root
    - group: root
    - require:
      - pkg: udhcpc
    - require_in:
      - service: qmi-manager

reboot-requested-after-qmi-udev-rules-changed:
  module.wait:
    - name: power.request_reboot

/etc/udev/rules.d/99-qmi.rules:
  file.managed:
    - source: salt://network/wwan/qmi/udev.rules
    - watch_in:
      - module: reboot-requested-after-qmi-udev-rules-changed
    - require_in:
      - service: qmi-manager

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
    - require_in:
      - service: qmi-manager

qmi-network-script-installed:
  file.managed:
    - name: /usr/bin/qmi-network
    - source: salt://network/wwan/qmi/qmi-network.sh
    - mode: 755
    - user: root
    - group: root
    - require:
      - pkg: libqmi-installed
    - require_in:
      - service: qmi-manager

qmi-manager-script-installed:
  file.managed:
    - name: /usr/bin/qmi-manager
    - source: salt://network/wwan/qmi/qmi-manager.sh
    - mode: 755
    - user: root
    - group: root
    - require:
      - pkg: libqmi-installed
    - require_in:
      - service: qmi-manager

qmi-manager-service-configured:
  file.managed:
    - name: /lib/systemd/system/qmi-manager.service
    - source: salt://network/wwan/qmi/qmi-manager.service
    - require:
      - file: qmi-manager-script-installed
    - require_in:
      - service: qmi-manager

qmi-manager-service-running:
  service.running:
    - name: qmi-manager
    - enable: true
    - require:
      - file: /lib/systemd/system/qmi-manager.service
    - watch:
      - file: /lib/systemd/system/qmi-manager.service
      - file: /etc/qmi-manager.conf
    - require_in:
      - service: qmi-manager
