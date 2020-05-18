
reboot-requested-after-kernel-changes:
  module.wait:
    - name: power.request_reboot

{% set _timestamp = None|strftime("%Y%m%d%H%M%S") %}

rtc-pcf8523-module-backed-up:
  file.copy:
    - name: /lib/modules/{{ salt['grains.get']('kernelrelease') }}/kernel/drivers/rtc/rtc-pcf8523.ko.{{ _timestamp }}
    - source: /lib/modules/{{ salt['grains.get']('kernelrelease') }}/kernel/drivers/rtc/rtc-pcf8523.ko
    - force: true
    - prereq:
      - file: rtc-pcf8523-module-updated
rtc-pcf8523-module-updated:
  file.managed:
    - name: /lib/modules/{{ salt['grains.get']('kernelrelease') }}/kernel/drivers/rtc/rtc-pcf8523.ko
    - source: salt://raspi/kernel/{{ salt['grains.get']('kernelrelease') }}/drivers/rtc/rtc-pcf8523.ko
    - hash: c51ccd940bc06a97769e8c12a7bec9fe9141b572
    - watch_in:
      - module: reboot-requested-after-kernel-changes
