
# TODO: Only applicable for spm 3.0+

rtc-i2c-present-test:
  cmd.run:
    - name: "i2cdetect -y 1 0x51 0x51 | grep UU"

# Applicable for all?
rtc-device-present-test:
  cmd.run:
    - name: "ls -la /dev/rtc"

rtc-dmesg-not-missing-test:
  cmd.run:
    - name: "dmesg | grep -c \"RTC chip is not present\" | grep 0"  # We expect to NOT have that line in dmesg

rtc-systohc-and-get-time-test:
  cmd.run:
    - name: "hwclock -w && hwclock -r"

