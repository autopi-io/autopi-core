
# TODO: Only applicable for spm 3.0+

spm-version-test:
  test.module:
    - name: spm.query
    - args:
      - version
    - validate: float(ret["value"]) >= 4.0

spm-volt-readout-test:
  test.module:
    - name: spm.query
    - args:
      - volt_readout
    - validate: ret["value"] >= 12.5

spm-volt-config-flags-test:
  test.module:
    - name: spm.query
    - args:
      - volt_config_flags
    - validate:
      - not ret["unsaved"]["limit"]
      - not ret["unsaved"]["factor"]
      - not ret["unsaved"]["ewma_alpha"]
      - not ret["unsaved"]["hibernate_level"]
      - not ret["unsaved"]["wake_change"]
      - not ret["unsaved"]["wake_level"]
    - require:
      - spm-version-test

