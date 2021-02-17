
filebeat-scrubber-service-disabled:
  service.dead:
    - name: filebeat-scrubber
    - enable: false

filebeat-scrubber-uninstalled:
  cmd.run:
    - name: pip3 uninstall filebeat-scrubber --yes
    - onlyif: "pip3 show filebeat-scrubber | grep 'Name: filebeat-scrubber'"

filebeat-uninstalled:
  pkg.removed:
    - name: filebeat