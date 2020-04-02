
reboot-requested-after-boot-config-changed:
  module.wait:
    - name: power.request_reboot

kernel-arguments-configured:
  file.managed:
    - name: /boot/cmdline.txt
    - source: salt://raspi/boot/cmdline.txt

gpio-poweroff-enabled:
  file.replace:
    - name: /boot/config.txt
    - pattern: "^#?dtoverlay=gpio-poweroff.*$"
    - repl: "dtoverlay=gpio-poweroff,gpiopin=4,active_low=y"
    - append_if_not_found: true
    - watch_in:
      - module: reboot-requested-after-boot-config-changed

gpio-shutdown-enabled:
  file.replace:
    - name: /boot/config.txt
    - pattern: "^#?dtoverlay=gpio-shutdown.*$"
    {%- if salt["pillar.get"]("power:firmware:version") in ["2.0"] %}
    - repl: "dtoverlay=gpio-shutdown,gpio_pin=25,active_low=n"
    {%- else %}
    - repl: "dtoverlay=gpio-shutdown,gpio_pin=12,gpio_pull=up"
    {%- endif %}
    - append_if_not_found: true
    - watch_in:
      - module: reboot-requested-after-boot-config-changed

i2c-module-enabled:
  file.replace:
    - name: /boot/config.txt
    - pattern: "^#?dtparam=i2c_arm.*$"
    - repl: "dtparam=i2c_arm=on"
    - append_if_not_found: true
i2c-module-reloaded:
  cmd.run:
    - name: modprobe i2c-bcm2708
    - onchanges:
      - file: i2c-module-enabled

i2c-dev-module-enabled:
  file.replace:
    - name: /etc/modules
    - pattern: "^#?i2c-dev$"
    - repl: "i2c-dev"
    - append_if_not_found: true
i2c-dev-module-reloaded:
  cmd.run:
    - name: modprobe i2c-dev
    - onchanges:
      - file: i2c-dev-module-enabled

splash-disabled:
  file.replace:
    - name: /boot/config.txt
    - pattern: "^#?disable_splash=.*$"
    - repl: "disable_splash=1"
    - append_if_not_found: true

warnings-disabled:
  file.replace:
    - name: /boot/config.txt
    - pattern: "^#?avoid_warnings=.*$"
    - repl: "avoid_warnings=1"
    - append_if_not_found: true

gpu-memory-configured:
  file.replace:
    - name: /boot/config.txt
    - pattern: "^#?gpu_mem=.*$"
    - repl: "gpu_mem={{ salt['pillar.get']('rpi:boot:gpu_mem', default='16') }}"
    - append_if_not_found: true

bluetooth-configured:
  file.replace:
    - name: /boot/config.txt
    - pattern: "^#?dtoverlay=pi3-(?:disable|miniuart)-bt$"
    - repl: "dtoverlay=pi3-{{ salt['pillar.get']('rpi:boot:bt', default='disable') }}-bt"
    - append_if_not_found: true

core-frequency-configured:
  file.replace:
    - name: /boot/config.txt
    - pattern: "^#?core_freq=.*$"
    {%- if salt['pillar.get']('rpi:boot:bt', default='disable') == 'miniuart' %}
    - repl: "core_freq=250"
    - append_if_not_found: true
    {%- else %}
    - repl: ""
    {%- endif %}

hciuart:
  {%- if salt['pillar.get']('rpi:boot:bt', default='disable') == 'miniuart' %}
  service.enabled:
    - unmask: true
  {%- else %}
  service.dead:
    - enable: false
  {%- endif %}

{% set _rtc = salt['pillar.get']('rpi:boot:rtc', default='') %}
rtc-configured:
  file.replace:
    - name: /boot/config.txt
    - pattern: "^#?dtoverlay=i2c-rtc.*$"
    {%- if _rtc %}
    - repl: "dtoverlay=i2c-rtc,{{ _rtc }}"
    - append_if_not_found: true
    {%- else %}
    - repl: "#dtoverlay=i2c-rtc,"
    {%- endif %}
    - watch_in:
      - module: reboot-requested-after-boot-config-changed

reboot-upon-changes-required:
  module.wait:
    - name: power.request_reboot
    - watch:
      - file: /boot/cmdline.txt
      - file: /boot/config.txt
