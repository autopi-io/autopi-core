include:
  - ec2x.startup
  - ec2x.gnss.update
#  - acc.config # TODO: Test this

update-release-retried:
  module.run:
    - name: minionutil.update_release
    - only_retry: true
