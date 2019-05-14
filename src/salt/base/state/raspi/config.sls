
pi-user-configured:
  user.present:
    - name: pi
    - password: '{{ salt['pillar.get']('user:pi:password') }}'
    - hash_password: True

pi-aliases-configured:
  file.managed:
    - name: /home/pi/.bash_aliases
    - contents:
      - alias autopitest="autopi state.sls checkout.test"
    - user: pi
    - group: pi
