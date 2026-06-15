# Ensures the /etc/apt/trusted.gpg keyring is in a valid state.
#   If it's not, it is replaced with an existing keyring, which needs to have the
#   backports and other keys added to it through the update process.
#   Requires trusted.gpg.os_release_{os_release_version} to be present to succeed

{%- if salt['grains.get']('osmajorrelease') in [9, 10] %}
# Backup old keyring if current is malformed
backup_trusted_gpg:
  file.managed:
    - name: /etc/apt/trusted.gpg.backup
    - source: /etc/apt/trusted.gpg
    - makedirs: True
    - onlyif: apt-key list 2>&1 | grep "ignored as the file has an unsupported filetype"

# Download new keyring
download_trusted_gpg:
  file.managed:
    - name: /etc/apt/trusted.gpg
    - source: salt://apt/keyring/trusted.gpg.os_release_{{ salt['grains.get']('osmajorrelease') }}
    - makedirs: True
    - require:
      - file: backup_trusted_gpg

{%- else %}
succeed_if_unsupported_version:
  test.succeed_without_changes:
    - name: Keyring check not supported for this os release version

{%- endif %}
