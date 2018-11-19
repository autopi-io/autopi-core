
update-release:
  module.run:
    - name: minionutil.update_release

# Restart minion if restart is pending after running update release
restart-minion-if-pending:
  module.run:
    - name: minionutil.request_restart
    - pending: false
    - immediately: true
    - reason: release_updated