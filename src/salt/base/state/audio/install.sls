
include:
  - .dac.config

old-files-cleared:
  file.absent:
    - name: /opt/autopi/audio/
    - prereq_in:
      - file: sound-folder-created

sound-folder-created:
  file.directory:
    - name: /opt/autopi/audio/sound

sound-files-distributed:
  file.recurse:
    - name: /opt/autopi/audio/sound
    - source: salt://audio/sound
    - clean: True

speak-event-folder-created:
  file.directory:
    - name: /opt/autopi/audio/speak/event

speak-event-system-network-wwan0-offline-generated:
  cmd.run:
    - name: espeak "Autopi, system network 4g offline" -v en-gb -p 50 -s 175 -g 10 -w /opt/audio/speak/event/system.network.wwan0.offline.wav
    - unless: test -f /opt/audio/speak/event/system.network.wwan0.offline.wav

speak-event-system-network-wwan0-online-generated:
  cmd.run:
    - name: espeak "Autopi, system network 4g online" -v en-gb -p 50 -s 175 -g 10 -w /opt/audio/speak/event/system.network.wwan0.online.wav
    - unless: test -f /opt/audio/speak/event/system.network.wwan0.online.wav

speak-event-system-power-hibernate-generated:
  cmd.run:
    - name: espeak "Autopi, system power hibernate" -v en-gb -p 50 -s 175 -g 10 -w /opt/audio/speak/event/system.power.hibernate.wav
    - unless: test -f /opt/audio/speak/event/system.power.hibernate.wav

speak-event-system-power-sleep-generated:
  cmd.run:
    - name: espeak "Autopi, system power sleep" -v en-gb -p 50 -s 175 -g 10 -w /opt/audio/speak/event/system.power.sleep.wav
    - unless: test -f /opt/audio/speak/event/system.power.sleep.wav

speak-event-system-release-failed-generated:
  cmd.run:
    - name: espeak "Autopi, system release failed" -v en-gb -p 50 -s 175 -g 10 -w /opt/audio/speak/event/system.release.failed.wav
    - unless: test -f /opt/audio/speak/event/system.release.failed.wav

speak-event-system-release-forcing-generated:
  cmd.run:
    - name: espeak "Autopi, system release forcing" -v en-gb -p 50 -s 175 -g 10 -w /opt/audio/speak/event/system.release.forcing.wav
    - unless: test -f /opt/audio/speak/event/system.release.forcing.wav

speak-event-system-release-pending-generated:
  cmd.run:
    - name: espeak "Autopi, system release pending" -v en-gb -p 50 -s 175 -g 10 -w /opt/audio/speak/event/system.release.pending.wav
    - unless: test -f /opt/audio/speak/event/system.release.pending.wav

speak-event-system-release-updated-generated:
  cmd.run:
    - name: espeak "Autopi, system release updated" -v en-gb -p 50 -s 175 -g 10 -w /opt/audio/speak/event/system.release.updated.wav
    - unless: test -f /opt/audio/speak/event/system.release.updated.wav

speak-event-vehicle-battery-critical_level-generated:
  cmd.run:
    - name: espeak "Autopi, vehicle battery critical level" -v en-gb -p 50 -s 175 -g 10 -w /opt/audio/speak/event/vehicle.battery.critical_level.wav
    - unless: test -f /opt/audio/speak/event/vehicle.battery.critical_level.wav