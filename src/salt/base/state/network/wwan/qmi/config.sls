
include:
  - minion.grains

/etc/qmi-network.conf:
  file.managed:
    - source: salt://network/wwan/qmi/qmi-network.conf.jinja
    - template: jinja
    - require:
      - sls: minion.grains

/etc/qmi-manager.conf:
  file.managed:
    - source: salt://network/wwan/qmi/qmi-manager.conf.jinja
    - template: jinja
    - require:
      - sls: minion.grains

/etc/qmi-sim.conf:
  {%- if salt['grains.get']('qmi:pin') %}
  file.managed:
    - source: salt://network/wwan/qmi/qmi-sim.conf.jinja
    - template: jinja
    - require:
      - sls: minion.grains
  {%- else %}
  file.absent
  {%- endif %}

/etc/udhcpc/qmi.override:
  file.managed:
    - source: salt://network/wwan/qmi/udhcpc.override.jinja
    - template: jinja
    - require:
      - sls: minion.grains

qmi-manager:
  service.running:
    - enable: true
    - watch:
      - file: /etc/qmi-network.conf
      - file: /etc/qmi-manager.conf
      - file: /etc/qmi-sim.conf
      - file: /etc/udhcpc/qmi.override