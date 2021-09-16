
# TODO: Future improvement is to check if git repo is corrupt (git fsck) and delete it entirely if it is

frontend-release-installed:
  git.latest:
    - name: "https://oauth2:2rJ32Xsb-12Z7XijePyS@gitlab.com/AutoPi.io/frontend_releases.git"
    - rev: 2021.09.18
    - force_reset: True
    - force_clone: True
    - force_fetch: True
    - target: /var/www/html
    - depth: 1
    - retry:
        attempts: 3
        interval: 3

frontend-env-file-created:
  file.managed:
    - name: /var/www/html/env.js
    - source: salt://ui/env.js.jinja
    - template: jinja
