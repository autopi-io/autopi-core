
include:
  - acc.test

  - audio.test

  - le910cx.test

  - obd.test

  - power.test
  - power.spm.test

  - raspi.test
  - raspi.hwclock.test
  - raspi.kernel.test

  - secure_element.test

no-op-test:
  cmd.run:
    - name: "echo 0"
    - require:
      - sls: acc.test

      - sls: audio.test

      - sls: le910cx.test

      - sls: obd.test

      - sls: power.test
      - sls: power.spm.test

      - sls: raspi.test
      - sls: raspi.hwclock.test
      - sls: raspi.kernel.test

      - sls: secure_element.test
