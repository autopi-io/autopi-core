
pi-user-configured:
  user.present:
    - name: pi
    - password: '{{ salt['pillar.get']('user:pi:password') }}'
    - hash_password: True

nmi-watchdog-enabled:
  file.line:
    - name: /etc/sysctl.conf
    - match: kernel.nmi_watchdog=0
    - mode: delete

rc-local-configured:
  file.managed:
    - name: /etc/rc.local
    - source: salt://raspi/rc.local.jinja
    - template: jinja

timezone-configured:
  timezone.system:
    - name: UTC

bluetooth-sap-disable-override-configured:
  file.managed:
    - name: /etc/systemd/system/bluetooth.service.d/01-disable-sap-plugin.conf
    - source: salt://raspi/bluetooth-service-override-sap.conf
    - makedirs: true