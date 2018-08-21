
scp -r src/salt/base/ext/* pi@local.autopi.io:~/core/ext/

ssh pi@local.autopi.io "
  pyclean /var/cache/salt/minion/extmods/
  sudo cp -fv ~/core/ext/_engines/*.py /var/cache/salt/minion/extmods/engines/
  sudo cp -fv ~/core/ext/_modules/*.py /var/cache/salt/minion/extmods/modules/
  sudo cp -fv ~/core/ext/_returners/*.py /var/cache/salt/minion/extmods/returners/
  sudo cp -fv ~/core/ext/_states/*.py /var/cache/salt/minion/extmods/states/
  sudo cp -fv ~/core/ext/_utils/*.py /var/cache/salt/minion/extmods/utils/
  sudo service salt-minion restart
  sudo service salt-minion status
"
