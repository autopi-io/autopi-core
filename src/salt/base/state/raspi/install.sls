
include:
  - .optimize
  - .boot
  - .udev
  - .config

hosts-file-configured:
  host.only:
    - name: 127.0.1.1
    - hostnames:
      - {{ salt['grains.get']('host') }}

pi-user-aliases-configured:
  file.managed:
    - name: /home/pi/.bash_aliases
    - contents:
      - alias autopitest="autopi state.sls checkout.test"
    - user: pi
    - group: pi
