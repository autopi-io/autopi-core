
reboot-requested-after-usb-udev-rules-changed:
  module.wait:
    - name: power.request_reboot

/etc/udev/rules.d/99-usb.rules:
  file.managed:
    - source: salt://raspi/udev/usb.rules.jinja
    - template: jinja
    - watch_in:
      - module: reboot-requested-after-usb-udev-rules-changed

udev-service-restarted-after-usb-rules-changed:
  service.running:
    - name: udev
    - watch:
      - file: /etc/udev/rules.d/99-usb.rules
