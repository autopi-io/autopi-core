
pi-user-configured:
  user.present:
    - name: pi
    - password: {{ salt['pillar.get']('user:pi:password') }}
    - hash_password: True
