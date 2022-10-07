
update-release-attempts-removed:
    grains.absent:
        - name: release:attempts
        - destructive: true
        - force: true
