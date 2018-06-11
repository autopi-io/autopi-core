
frontend-release-installed:
  git.latest:
    - name: "https://oauth2:2rJ32Xsb-12Z7XijePyS@gitlab.com/AutoPi.io/frontend_releases.git"
    - rev: 60d99a6a739f77db3e49f50d56f296bc4500f3fe
    - force_reset: True
    - force_clone: True
    - target: /var/www/html

frontend-env-file-created:
  file.managed:
    - name: /var/www/html/env.js
    - source: salt://ui/env.js.jinja
    - template: jinja
