
include:
  - .test

cryptoauth-info-serialized:
  module_extra.serialized:
    - name: cryptoauth.query
    - args:
      - serial
      - device
    - target: /tmp/cryptoauth.yml
    - format: yaml

test-result:
  module.run:
    - name: spm.query
    - cmd: hibernate_volt_level
    - kwargs:
        duration: 240001
        threshold: 12.3
    - require:
      - module_extra: cryptoauth-info-serialized
      - sls: checkout.test
