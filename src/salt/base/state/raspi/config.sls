
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

{%- if salt['grains.get']('osmajorrelease') == 10 %}
{%- if salt['pillar.get']('rpi:boot:bt', default='disable') == 'enable' %}
backports-repo-added:
  pkgrepo.managed:
    - name: deb http://deb.debian.org/debian buster-backports main
    - keyid: 648ACFD622F3D138
    - keyserver: keyserver.ubuntu.com

bluez-upgraded:
  pkg.installed:
    - name: bluez
    - version: 5.54-1~bpo10+1
    - require:
      - pkgrepo: backports-repo-added

bluetooth-sap-disable-override-configured:
  file.managed:
    - name: /etc/systemd/system/bluetooth.service.d/01-disable-sap-plugin.conf
    - source: salt://raspi/bluetooth-service-override-sap.conf
    - makedirs: true
{%- endif %}
{%- endif %}