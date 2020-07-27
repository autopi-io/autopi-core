
reboot-requested-after-kernel-changes:
  module.wait:
    - name: power.request_reboot

{%- if salt['grains.get']('kernelrelease') == '4.19.66-v7+' %}
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
    - hash: 615986eb32b6d12e51f6d1f23a5b976728f51f60
    - watch_in:
      - module: reboot-requested-after-kernel-changes
{%- else %}
rtc-pcf8523-module-not-updated:
  test.succeed_with_changes:
    - name: No updated 'pcf8523' RTC driver available for kernel release {{ salt['grains.get']('kernelrelease') }}
{%- endif %}