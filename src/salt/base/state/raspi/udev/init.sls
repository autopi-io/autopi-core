
reboot-requested-after-udev-changes:
  module.wait:
    - name: power.request_reboot

udev-usb-rules-configured:
  file.managed:
    - name: /etc/udev/rules.d/99-usb.rules
    - source: salt://raspi/udev/usb.rules.jinja
    - template: jinja
    - watch_in:
      - module: reboot-requested-after-udev-changes

# Required by 'usbmount' to work
{%- if salt["grains.get"]("osmajorrelease") == 9 %}
udev-mount-flag-shared-configured:
  file.replace:
    - name: /lib/systemd/system/systemd-udevd.service
    - pattern: "^#?MountFlags=.*$"
    - repl: "MountFlags=shared"
    - append_if_not_found: true
    - watch_in:
      - module: reboot-requested-after-udev-changes
{%- elif salt["grains.get"]("osmajorrelease") >= 10 %}
udev-no-private-mounts-configured:
  file.replace:
    - name: /lib/systemd/system/systemd-udevd.service
    - pattern: "^#?PrivateMounts=.*$"
    - repl: "PrivateMounts=no"
    - append_if_not_found: true
    - watch_in:
      - module: reboot-requested-after-udev-changes
{%- endif %}

udev-service-restarted-after-usb-rules-changed:
  service.running:
    - name: udev
    - watch:
      - file: /etc/udev/rules.d/99-usb.rules

udev-rtc-rules-configured:
  file.managed:
    - name: /etc/udev/rules.d/99-rtc.rules
    - source: salt://raspi/udev/rtc.rules.jinja
    - template: jinja

{%- if salt["pillar.get"]("minion:hw.version") >= 6.0 %}
udev-can-rules-configured:
  file.managed:
    - name: /etc/udev/rules.d/70-can.rules
    - source: salt://raspi/udev/can.rules.jinja
    - template: jinja
{%- endif %}