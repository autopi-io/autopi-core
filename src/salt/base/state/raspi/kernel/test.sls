
no-kernel-usb-errors-test:
  cmd.run:
    - name: "dmesg | grep -c \"usb .*error\" | grep 0"  # We expect to NOT have that line in dmesg

