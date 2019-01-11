
minion:
  master: master.autopi.io
  transport: zeromq
  zmq_monitor: True
  tcp_keepalive: True
  tcp_keepalive_idle: 10
  tcp_keepalive_cnt: 3
  tcp_keepalive_intvl: 10
  log_level_logfile: info
  cache_jobs: True
  keep_jobs: 336  # In hours
  minion_pillar_cache: True
  #grains_cache: True  # TODO: When enabled it does not seem to refresh upon update or saltutil.refresh_grains
  grains_cache_expiration: 3600 # Secs
  mine_enabled: False
  startup_states: sls
  sls_list:
    - ec2x.startup
    - ec2x.gnss.update
#    - acc.config # TODO: Test this
  return: event  # Publish job execution result notifications on the Minion event bus
  beacons_before_connect: True
  scheduler_before_connect: True
#  whitelist_modules:
#    - cmd
#    - config
#    - environ
#    - event
#    - file
#    - git
#    - grains
#    - network
#    - pillar
#    - pip
#    - pkg
#    - ps
#    - saltutil
#    - state
#    - system
#    - test
#    - timezone
#    # Ext
#    - acc
#    - audio
#    - cloud
#    - ec2x
#    - obd
#    - qmi
  cloud_cache:
    redis:
      host: localhost
      port: 6379
      db: 1
    max_batch_size: 500
    retry_count: 3
    fail_ttl: 604800  # One week

  engines:
    - tracking_manager:
        serial_conn:
          device: /dev/ttyUSB1
          baudrate: 115200
          timeout: 10
        returner: cloud
        workers:
          - name: poll_logger
            interval: 5
            messages:
                - handler: gnss_query
                  args:
                    - location
                  kwargs:
                    mode: 2
                  converter: gnss_location_to_position
                  returner: significant_position
#          - name: stream_logger
#            messages:
#                - handler: nmea0183_readout
#                  converter: nmea0183_readout_to_position
#                  returner: significant_position
    - event_reactor:
        mappings:
          # Forward specific events to cloud
          - regex: ^(battery|engine|position|power|release)/.*
            keyword_resolve: True
            actions:
              - handler: returner
                args:
                  - cloud.returner_event
                  - $event
          # Reset sleep timer when engine is running
          - regex: ^vehicle/engine/running
            actions:
              - handler: module_direct
                args:
                  - power.sleep_timer
                kwargs:
                  enable: False
          # Set sleep timer when engine is stopped
          - regex: ^vehicle/engine/stopped
            actions:
              - handler: module_direct
                args:
                  - power.sleep_timer
                kwargs:
                  enable: True
                  period: 1800
                  interval: 3600
                  reason: engine_stopped
          # Set sleep timer when powered on after sleep
          - regex: ^system/power/on
            condition: $event["data"]["trigger"] == "timer"
            actions:
              - handler: module_direct
                args:
                  - power.sleep_timer
                kwargs:
                  enable: True
                  period: 600
                  interval: 3600
                  reason: inactivity
          # Upload data to cloud before going to sleep
          - regex: ^system/power/(sleep|reboot)
            actions:
              - handler: module
                args:
                  - cloud.upload_batch
    - spm_manager:
        workers:
          - name: heartbeat
            delay: 10  # Give SPM some time to reset communication after GPIO pins have been setup
            interval: 60  # Run every minute
            messages:
                - handler: heartbeat
    - obd_manager:
        serial_conn:
          device: /dev/serial0
          baudrate: 9600
          timeout: 1
        returner: cloud
        workers:
          - name: realtime_readout
            interval: 1
            messages:
              - args:
                  - ELM_VOLTAGE
                kwargs:
                  force: True
                converter: battery
                returner: alternating_value
              - args:
                  - RPM
                kwargs:
                  force: True
          - name: frequent_readout
            interval: 30
            messages:
              - args:
                  - SPEED
                kwargs:
                  force: True
                returner: alternating_value
              - args:
                  - ENGINE_LOAD
                kwargs:
                  force: True
                returner: alternating_value
              - args:
                  - COOLANT_TEMP
                kwargs:
                  force: True
                returner: alternating_value
              - args:
                  - FUEL_LEVEL
                kwargs:
                  force: True
                returner: alternating_value
              - args:
                  - FUEL_RATE
                kwargs:
                  force: True
                returner: alternating_value
              - args:
                  - INTAKE_TEMP
                kwargs:
                  force: True
                returner: alternating_value
              - args:
                  - AMBIANT_AIR_TEMP
                kwargs:
                  force: True
                returner: alternating_value
    - acc_manager:
        i2c_conn:
          port: 1
          address: 0x1c
    - ec2x_manager:
        serial_conn:
          device: /dev/ttyUSB2
          baudrate: 115200
          timeout: 30  # Modem has long internal timeouts
    - api_service:
        flask:
          port: 9000

#    - audio_broker:
#        mixer:
#          frequency: 44100
#          bit_size: -16
#          channels: 2
#          buffer_size: 2048

# WiFi hotspot
hostapd:
  cardlist:
    uap0:                                  # The interface used by the AP
      driver: nl80211                      # Use the nl80211 driver with the brcmfmac driver
      hw_mode: g                           # Use the 2.4GHz band (g)
      channel: 6                           # Use channel 6
      ignore_broadcast_ssid: 0             # Enable SSID broadcast
      auth_algs: 1                         # Use Open System Authentication
      #ieee80211d: 1                        # Limit the frequencies used to those allowed in the country
      #country_code: DK                     # The country code
# Raspberry Pi 3
#      ieee80211n: 1                        # Enable 802.11n
#      wmm_enabled: 1                       # QoS support
      ap_list:
        AutoPi-{{ grains["id"][-12:] }}:   # The name of the AP
          auth_algs: 1                     # 1=WPA, 2=WEP, 3=Both
          wpa: 2                           # Use WPA2
          wpa_key_mgmt: WPA-PSK            # Use a pre-shared key
          wpa_pairwise: TKIP
          rsn_pairwise: CCMP               # Use AES, instead of TKIP
          wpa_passphrase: autopi2018

# DNS server for WiFi hotspot
dnsmasq:
  dnsmasq_conf: salt://dnsmasq/files/dnsmasq.conf
  dnsmasq_hosts: salt://dnsmasq/files/dnsmasq.hosts
  settings:
    interface:
      - uap0
    dhcp-range: 192.168.4.2,192.168.4.20,255.255.255.0,24h
    domain-needed: true
  hosts:
    local.autopi.io: 192.168.4.1

# Quectel EC2X modem
ec2x:
  error_format: 2
  urc_port: usbmodem
  gnss:
    auto_start: true
    nmea_port: none
    assist:
      enabled: true
      data_urls:
        - https://xtrapath1.izatcloud.net/xtra2.bin
        - https://xtrapath2.izatcloud.net/xtra2.bin
        - https://xtrapath3.izatcloud.net/xtra2.bin
      data_valid_mins: 720

# Cloud API
cloud_api:
  url: https://api.autopi.io/

power:
  firmware:
    version: 1.1.1.0
    auto_update: true

