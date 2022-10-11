
acc-xyz-test:
  test.module:
    - name: acc.query
    - args:
      - xyz
    - validate:
      - abs(ret["x"] - 0.0) < 0.1
      - abs(ret["y"] - 0.0) < 0.1
      - abs(ret["z"] - -1.0) < 0.1

acc-interrupt-timeout-check:
  test.module:
    - name: acc.manage
    - args:
      - context
    - validate:
      - ret["interrupt"]["timeout"] <= 2
      - ret["interrupt"]["total"] > 0

