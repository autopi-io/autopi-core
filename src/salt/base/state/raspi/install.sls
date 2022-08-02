
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
    - contents: |
        function hwtest() {
            [[ ! ("$#" == 1 && $1 =~ ^6\.[0-3]$) ]] && { echo 'Invalid or unsupported HW version specified' >&2; return 1; }
            autopi state.sls checkout.hw pillar="{'minion': {'hw.version': $1}, 'allow_reboot': true}" 2>&1 | tee ~/hwtest.out | less -r +G && sudo bash -c "cat /home/pi/hwtest.out >> "/media/usb/hwtest-$(sed -rn "s/^value:\s([0-9a-f]+)$/\1/p" /tmp/secure-element.yml).out"" && echo "Wrote result to USB drive mounted at /media/usb/"
        }
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
