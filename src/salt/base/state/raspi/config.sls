
include:
  - .optimize
  - .boot
  - .udev

pi-user-configured:
  user.present:
    - name: pi
    - password: autopi2018
    - hash_password: True
