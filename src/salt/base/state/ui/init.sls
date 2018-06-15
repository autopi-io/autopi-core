
frontend-release-installed:
  git.latest:
    - name: "https://oauth2:2rJ32Xsb-12Z7XijePyS@gitlab.com/AutoPi.io/frontend_releases.git"
    - rev: 671abc78ab4c75226f417e6ee861e3fd1ad9acd6
    - force_reset: True
    - force_clone: True
    - target: /var/www/html

frontend-env-file-created:
  file.managed:
    - name: /var/www/html/env.js
    - source: salt://ui/env.js.jinja
    - template: jinja
