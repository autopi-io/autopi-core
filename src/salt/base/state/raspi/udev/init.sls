
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

{%- if salt["grains.get"]("osmajorrelease") == 9 %}
# Required by 'usbmount' to work
udev-mount-flag-shared-configured:
  file.replace:
    - name: /lib/systemd/system/systemd-udevd.service
    - pattern: "^#?MountFlags=.*$"
    - repl: "MountFlags=shared"
    - append_if_not_found: true
    - watch_in:
      - module: reboot-requested-after-udev-changes
{%- endif %}

udev-service-restarted-after-usb-rules-changed:
  service.running:
    - name: udev
    - watch:
      - file: /etc/udev/rules.d/99-usb.rules
