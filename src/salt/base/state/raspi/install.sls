
include:
  - .optimize
  - .boot
  - .kernel
  - .udev
  - .hwclock
  - .config
  - .swap
  - .patch

hosts-file-configured:
  host.only:
    - name: 127.0.1.1
    - hostnames:
      - {{ salt['grains.get']('host') }}

pi-user-aliases-configured:
  file.managed:
    - name: /home/pi/.bash_aliases
    - contents:
      - alias hwtest='autopi state.sls checkout.hw 2>&1 | tee ~/hwtest.out | less -r +G && sudo bash -c "cat /home/pi/hwtest.out >> "/media/usb/hwtest-$(sed -rn "s/^serial:\s([0-9a-f]+)$/\1/p" /tmp/cryptoauth.yml).out"" && echo "Wrote result to USB drive mounted at /media/usb/"'
    - user: pi
    - group: pi

haveged-installed:
  pkg.installed:
    - name: haveged

haveged-service-running:
  service.running:
    - name: haveged

fake-hwclock-configured:
  {%- if salt['pillar.get']('rpi:hwclock:use_fake', default=True) %}
  pkg.installed:
  {%- else %}
  pkg.purged:
  {%- endif %}
    - name: fake-hwclock
