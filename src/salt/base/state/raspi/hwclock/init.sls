
hwclock-script-configured:
  file.managed:
    - name: /lib/udev/hwclock-set
    - source: salt://raspi/hwclock/hwclock-set.jinja
    - template: jinja

rtc-device-systemd-enabled:
  file.replace:
    - name: /lib/udev/rules.d/85-hwclock.rules
    - pattern: '^.*KERNEL=="rtc0".*$'
    - repl: 'KERNEL=="rtc0", RUN+="/lib/udev/hwclock-set $root/$name", TAG+="systemd"'
    - append_if_not_found: true

timesyncd-service-wants-rtc-device-configured:
  file.line:
    - name: /lib/systemd/system/systemd-timesyncd.service
    - content: 'Wants=dev-rtc.device'
    - mode: ensure
    - after: 'Wants=.+'

timesyncd-service-after-rtc-device-configured:
  file.line:
    - name: /lib/systemd/system/systemd-timesyncd.service
    - content: 'After=dev-rtc.device'
    - mode: ensure
    - after: 'After=.+'

timesyncd-service-reloaded:
  module.run: 
    - name: service.systemctl_reload
    - onchanges:
      - file: /lib/systemd/system/systemd-timesyncd.service

{%- if salt['pillar.get']('rpi:boot:rtc', default='').startswith('pcf85063a') %}
rtc-retry-script-installed:
  file.managed:
    - name: /usr/bin/rtc-retry
    - source: salt://raspi/hwclock/rtc-retry.sh.jinja
    - mode: 755
    - user: root
    - group: root
{%- endif %}