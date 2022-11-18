
reboot-requested-after-boot-config-changed:
  module.wait:
    - name: power.request_reboot

kernel-arguments-configured:
  file.managed:
    - name: /boot/cmdline.txt
    - source: salt://raspi/boot/cmdline.txt.jinja
    - template: jinja

temporary-config-prepared:
  file.managed:
    - name: /boot/config.txt.tmp
    - source: /boot/config.txt
    - mode: 755

audio-default-disabled:
  file.replace:
    - name: /boot/config.txt.tmp
    - pattern: "^dtparam=audio=on.*$"
    - repl: "#dtparam=audio=on"
    - append_if_not_found: true
    - require:
      - file: temporary-config-prepared
    - require_in:
      - file: temporary-config-applied
    - watch_in:
      - module: reboot-requested-after-boot-config-changed

audio-i2c-mmap-configured:
  file.replace:
    - name: /boot/config.txt.tmp
    - pattern: "^#?dtoverlay=i2s-mmap.*$"
    - repl: "dtoverlay=i2s-mmap"
    - append_if_not_found: true
    - require:
      - file: temporary-config-prepared
    - require_in:
      - file: temporary-config-applied
    - watch_in:
      - module: reboot-requested-after-boot-config-changed

audio-hifiberry-dac-configured:
  file.replace:
    - name: /boot/config.txt.tmp
    - pattern: "^#?dtoverlay=hifiberry-dac.*$"
    - repl: "dtoverlay=hifiberry-dac"
    - append_if_not_found: true
    - require:
      - file: temporary-config-prepared
    - require_in:
      - file: temporary-config-applied
    - watch_in:
      - module: reboot-requested-after-boot-config-changed

gpio-poweroff-enabled:
  file.replace:
    - name: /boot/config.txt.tmp
    - pattern: "^#?dtoverlay=gpio-poweroff.*$"
    - repl: "dtoverlay=gpio-poweroff,gpiopin=4,active_low=y"
    - append_if_not_found: true
    - require:
      - file: temporary-config-prepared
    - require_in:
      - file: temporary-config-applied
    - watch_in:
      - module: reboot-requested-after-boot-config-changed

gpio-shutdown-enabled:
  file.replace:
    - name: /boot/config.txt.tmp
    - pattern: "^#?dtoverlay=gpio-shutdown.*$"
    {%- if salt["pillar.get"]("minion:spm.version", default=3.0) >= 2.0 %}
    - repl: "dtoverlay=gpio-shutdown,gpio_pin=25,gpio_pull=down,active_low=n"
    {%- else %}
    - repl: "dtoverlay=gpio-shutdown,gpio_pin=12,gpio_pull=up"
    {%- endif %}
    - append_if_not_found: true
    - require:
      - file: temporary-config-prepared
    - require_in:
      - file: temporary-config-applied
    - watch_in:
      - module: reboot-requested-after-boot-config-changed

{%- if salt["pillar.get"]("minion:hw.version", default=0.0) >= 7.0 %}
usb-xhci-controller-enabled:
  file.replace:
    - name: /boot/config.txt.tmp
    - pattern: "^#?otg_mode=.*$"
    - repl: "otg_mode=1"
    - append_if_not_found: true
    - require:
      - file: temporary-config-prepared
    - require_in:
      - file: temporary-config-applied
    - watch_in:
      - module: reboot-requested-after-boot-config-changed

i2c0-module-enabled:
  file.replace:
    - name: /boot/config.txt.tmp
    - pattern: "^#?(dtparam=i2c_vc|dtoverlay=i2c0).*$"
    - repl: "dtoverlay=i2c0,pins_44_45=on"
    - append_if_not_found: true
    - require:
      - file: temporary-config-prepared
    - require_in:
      - file: temporary-config-applied
    - watch_in:
      - module: reboot-requested-after-boot-config-changed

i2c1-module-enabled:
  file.replace:
    - name: /boot/config.txt.tmp
    - pattern: "^#?(dtparam=i2c_arm|dtoverlay=i2c1).*$"
    - repl: "dtoverlay=i2c1"
    - append_if_not_found: true
    - require:
      - file: temporary-config-prepared
    - require_in:
      - file: temporary-config-applied
    - watch_in:
      - module: reboot-requested-after-boot-config-changed

# Generated with: dtc -@ -I dts -O dtb -o disable-pcie.dtbo disable-pcie-overlay.dts
disable-pcie-overlay-distributed:
  file.managed:
    - name: /boot/overlays/disable-pcie.dtbo
    - source: salt://raspi/boot/overlays/disable-pcie.dtbo
    - source_hash: salt://raspi/boot/overlays/disable-pcie.dtbo.sha1
    - mode: 755

disable-pcie-overlay-configured:
  file.replace:
    - name: /boot/config.txt.tmp
    - pattern: "^#?dtoverlay=disable-pcie$"
    - repl: "dtoverlay=disable-pcie"
    - append_if_not_found: true
    - require:
      - file: disable-pcie-overlay-distributed
      - file: temporary-config-prepared
    - require_in:
      - file: temporary-config-applied

{%- else %}
i2c-module-enabled:
  file.replace:
    - name: /boot/config.txt.tmp
    - pattern: "^#?dtparam=i2c_arm.*$"
    - repl: "dtparam=i2c_arm=on"
    - append_if_not_found: true
    - require:
      - file: temporary-config-prepared
    - require_in:
      - file: temporary-config-applied
i2c-module-reloaded:
  cmd.run:
    - name: modprobe i2c-bcm2708
    - onchanges:
      - file: i2c-module-enabled
{%- endif %}

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
    - name: /boot/config.txt.tmp
    - pattern: "^#?disable_splash=.*$"
    - repl: "disable_splash=1"
    - append_if_not_found: true
    - require:
      - file: temporary-config-prepared
    - require_in:
      - file: temporary-config-applied

warnings-disabled:
  file.replace:
    - name: /boot/config.txt.tmp
    - pattern: "^#?avoid_warnings=.*$"
    - repl: "avoid_warnings=1"
    - append_if_not_found: true
    - require:
      - file: temporary-config-prepared
    - require_in:
      - file: temporary-config-applied

gpu-memory-configured:
  file.replace:
    - name: /boot/config.txt.tmp
    - pattern: "^#?gpu_mem=.*$"
    - repl: "gpu_mem={{ salt['pillar.get']('rpi:boot:gpu_mem', default='16') }}"
    - append_if_not_found: true
    - require:
      - file: temporary-config-prepared
    - require_in:
      - file: temporary-config-applied

bluetooth-configured:
  file.replace:
    - name: /boot/config.txt.tmp
    - pattern: "^#?dtoverlay=(?:pi3-)?(?:disable|miniuart)-bt$"
    {%- if salt['pillar.get']('rpi:boot:bt', default='disable') == 'enable' %}
    - repl: ""
    {%- else %}
    - repl: "dtoverlay=pi3-{{ salt['pillar.get']('rpi:boot:bt', default='disable') }}-bt"
    - append_if_not_found: true
    {%- endif %}
    - require:
      - file: temporary-config-prepared
    - require_in:
      - file: temporary-config-applied

core-frequency-configured:
  file.replace:
    - name: /boot/config.txt.tmp
    - pattern: "^#?core_freq=.*$"
    {%- if salt['pillar.get']('rpi:boot:bt', default='disable') == 'miniuart' %}
    - repl: "core_freq=250"
    - append_if_not_found: true
    {%- else %}
    - repl: ""
    {%- endif %}
    - require:
      - file: temporary-config-prepared
    - require_in:
      - file: temporary-config-applied

hciuart:
  {%- if salt['pillar.get']('rpi:boot:bt', default='disable') in ['enable', 'miniuart'] %}
  service.enabled:
    - unmask: true
  {%- else %}
  service.dead:
    - enable: false
  {%- endif %}

{% set _rtc = salt['pillar.get']('rpi:boot:rtc', default='pcf85063a') %}
rtc-configured:
  file.replace:
    - name: /boot/config.txt.tmp
    - pattern: "^#?dtoverlay=i2c-rtc.*$"
    {%- if _rtc %}
    - repl: "dtoverlay=i2c-rtc,{{ _rtc }}"
    - append_if_not_found: true
    {%- else %}
    - repl: "#dtoverlay=i2c-rtc,"
    {%- endif %}
    - require:
      - file: temporary-config-prepared
    - require_in:
      - file: temporary-config-applied
    - watch_in:
      - module: reboot-requested-after-boot-config-changed

{%- for key, val in salt["pillar.get"]("rpi:boot:gpio", default={}).iteritems() %}
gpio-{{ key }}-configured:
  file.replace:
    - name: /boot/config.txt.tmp
    - pattern: "^#?gpio={{ key }}=.*$"
    - repl: "gpio={{ key }}={{ val }}"
    - append_if_not_found: true
    - require:
      - file: temporary-config-prepared
    - require_in:
      - file: temporary-config-applied
    - watch_in:
      - module: reboot-requested-after-boot-config-changed
{%- endfor %}

{%- if salt["pillar.get"]("minion:hw.version", default=0.0) >= 6.0 %}
spi-module-enabled:
  file.replace:
    - name: /boot/config.txt.tmp
    - pattern: "^#?dtparam=spi.*$"
    - repl: "dtparam=spi=on"
    - append_if_not_found: true
    - require:
      - file: temporary-config-prepared
    - require_in:
      - file: temporary-config-applied
    - watch_in:
      - module: reboot-requested-after-boot-config-changed

can1-configured:
  file.replace:
    - name: /boot/config.txt.tmp
    - pattern: "^#?dtoverlay=mcp251(xfd|5|5-can1),spi0-1.*$"
    {%- if salt["pillar.get"]("minion:hw.version") >= 7.0 %}
    - repl: "dtoverlay=mcp2515,spi0-1,interrupt=17,oscillator=8000000,speed=20000000"
    {%- elif salt["pillar.get"]("minion:hw.version") in [6.0, 6.2] %}
    - repl: "dtoverlay=mcp251xfd,spi0-1,interrupt=15,oscillator=40000000,speed=20000000"
    {%- else %}
    - repl: "dtoverlay=mcp2515,spi0-1,interrupt=15,oscillator=8000000,speed=20000000"
    {%- endif %}
    - append_if_not_found: true
    - require:
      - file: temporary-config-prepared
    - require_in:
      - file: temporary-config-applied
    - watch_in:
      - module: reboot-requested-after-boot-config-changed

can0-configured:
  file.replace:
    - name: /boot/config.txt.tmp
    - pattern: "^#?dtoverlay=mcp251(xfd|5|5-can0),spi0-0.*$"
    {%- if salt["pillar.get"]("minion:hw.version") >= 7.0 %}
    - repl: "dtoverlay=mcp2515,spi0-0,interrupt=16,oscillator=8000000,speed=20000000"
    {%- elif salt["pillar.get"]("minion:hw.version") == 6.0 %}
    - repl: "dtoverlay=mcp251xfd,spi0-0,interrupt=14,oscillator=40000000,speed=20000000"
    {%- else %}
    - repl: "dtoverlay=mcp2515,spi0-0,interrupt=14,oscillator=8000000,speed=20000000"
    {%- endif %}
    - append_if_not_found: true
    - require:
      - file: temporary-config-prepared
    - require_in:
      - file: temporary-config-applied
    - watch_in:
      - module: reboot-requested-after-boot-config-changed

{%- endif %}

temporary-config-applied:
  cmd.run:
    - name: mv -f /boot/config.txt.tmp /boot/config.txt
    - onlyif: "diff -q /boot/config.txt /boot/config.txt.tmp | fgrep 'Files /boot/config.txt and /boot/config.txt.tmp differ'"

reboot-upon-changes-required:
  module.wait:
    - name: power.request_reboot
    - watch:
      - file: /boot/cmdline.txt
      - cmd: temporary-config-applied

{%- if salt["pillar.get"]("allow_reboot", default=False) %}
reboot-immediately-if-allowed-and-pending:
  module.run:
    - name: power.request_reboot
    - pending: false
    - immediately: true
    - delay: 2
    - reason: raspi_boot_config_changes
{%- endif %}
