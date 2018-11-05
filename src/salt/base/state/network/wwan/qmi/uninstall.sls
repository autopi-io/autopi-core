
qmi-manager-service-dead:
  service.dead:
    - name: qmi-manager

qmi-manager-service-deconfigured:
  file.absent:
    - name: /lib/systemd/system/qmi-manager.service
    - require:
      - service: qmi-manager-service-dead
