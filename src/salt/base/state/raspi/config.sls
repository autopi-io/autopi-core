
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
apt-debian-backport-keys:
  cmd.run:
    - name: apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 0E98404D386FA1D9 && apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 6ED0E7B82643E131

{%- if salt['pillar.get']('rpi:boot:bt', default='disable') == 'enable' %}

bluez-expired-backports-repo-removed:
  pkgrepo.absent:
    - name: deb http://deb.debian.org/debian buster-backports main
    - refresh: false
    - require:
      - cmd: apt-debian-backport-keys

bluez-archive-backports-repo-added:
  pkgrepo.managed:
    - name: deb http://archive.debian.org/debian buster-backports main
    - require:
      - cmd: apt-debian-backport-keys

bluez-upgraded:
  pkg.installed:
    - name: bluez
    - version: 5.54-1~bpo10+1
    - require:
      - pkgrepo: bluez-archive-backports-repo-added

bluetooth-sap-disable-override-configured:
  file.managed:
    - name: /etc/systemd/system/bluetooth.service.d/01-disable-sap-plugin.conf
    - source: salt://raspi/bluetooth-service-override-sap.conf
    - makedirs: true
{%- endif %}
{%- endif %}