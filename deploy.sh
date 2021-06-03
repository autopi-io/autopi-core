
scp -r src/salt/base/ext/* pi@192.168.8.104:~/core/ext/

ssh pi@192.168.8.104 "
  pyclean /var/cache/salt/minion/extmods/
  sudo cp -fv ~/core/ext/_engines/*.py /var/cache/salt/minion/extmods/engines/
  sudo cp -fv ~/core/ext/_modules/*.py /var/cache/salt/minion/extmods/modules/
  sudo cp -fv ~/core/ext/_returners/*.py /var/cache/salt/minion/extmods/returners/
  sudo cp -fv ~/core/ext/_states/*.py /var/cache/salt/minion/extmods/states/
  sudo cp -fv ~/core/ext/_utils/*.py /var/cache/salt/minion/extmods/utils/
  sudo service salt-minion restart
  sudo service salt-minion status
"
