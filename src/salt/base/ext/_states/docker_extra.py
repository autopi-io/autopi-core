import re

def container_absent_except(name, projects, force=False):
    '''
    Ensure that all containers except those that match the project names are absent.
    This state must be run with all project names in one go, do not use the name field.

    projects
        List of project names that will be excempted from being absent.

    force : False
        Set to ``True`` to remove the container even if it is running

    Usage Examples:

    .. code-block:: yaml

        project_slug:
          docker_extra.container_absent_except

        multiple_projects:
          docker_extra.container_absent_except:
            - projects:
              - project_name
              - project_name
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    containers = __salt__['docker.list_containers'](all=True)

    if not containers:
        ret['result'] = True
        ret['comment'] = 'No containers'
        return ret

    # Find unknown containers
    to_remove = []
    for container_name in containers:
        print(container_name)
        if not [x for x in projects if container_name.startswith(x)]:
            to_remove.append(container_name)

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = ('Containers \'{0}\' will be removed'.format(to_remove))
        return ret

    # Iterate over matches
    stop_errors = []
    for target in to_remove:
        try:
            changes = __salt__['docker.rm'](target, force=force)
            ret['changes'][target] = changes
        except Exception:
            stop_errors.append(changes)

    if stop_errors:
        ret['comment'] = '; '.join(stop_errors)
        return ret

    ret['result'] = True
    ret['comment'] = (
        'The following container(s) were removed: {0}'
        .format(', '.join(to_remove))
    )

    return ret
