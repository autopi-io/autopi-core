
frontend-release-installed:
  git.latest:
    - name: "https://oauth2:2rJ32Xsb-12Z7XijePyS@gitlab.com/AutoPi.io/frontend_releases.git"
    - rev: 1be75e3980ce3507eb32b1d63a6376e26af1747c
    - force_reset: True
    - force_clone: True
    - target: /var/www/html

frontend-env-file-created:
  file.managed:
    - name: /var/www/html/env.js
    - source: salt://ui/env.js.jinja
    - template: jinja
