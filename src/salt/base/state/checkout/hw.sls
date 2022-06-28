
include:
  {%- if salt['pillar.get']('minion:hw.version', 0.0) > 0.0 %}
  - raspi.boot
  {%- endif %}
  - .test

spm-bod-fuse-configured:
  module_extra.configured:
    - name: spm.fuse
    - args:
      - h
      - t88
    - kwargs:
        value: "0xde"
        confirm: true

secure-element-info-serialized:
  module_extra.serialized:
    - name: crypto.query
    - args:
      - serial_number
    - target: /tmp/secure-element.yml
    - format: yaml

test-result:
  module.run:
    - name: spm.query
    - cmd: hibernate_volt_level
    - kwargs:
        duration: 240001
        threshold: 12.3
    - require:
      - module_extra: secure-element-info-serialized
      - sls: checkout.test
