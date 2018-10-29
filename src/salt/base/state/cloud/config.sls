
_cloud_cache_upload_frequent:
  schedule.present:
    - function: cloud.upload_cache
    - minutes: 1
    - maxrunning: 1
    - run_on_start: false
    - return_job: false

_cloud_cache_upload_infrequent:
  schedule.present:
    - function: cloud.upload_cache
    - job_kwargs:
        include_failed: true
    - hours: 12
    - maxrunning: 1
    - run_on_start: true
    - return_job: false
