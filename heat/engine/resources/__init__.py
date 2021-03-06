# vim: tabstop=4 shiftwidth=4 softtabstop=4

#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import os
import os.path

from oslo.config import cfg

from heat.common import environment_format
from heat.openstack.common import log
from heat.openstack.common.gettextutils import _
from heat.engine import environment


LOG = log.getLogger(__name__)


def _register_resources(env, type_pairs):

    for res_name, res_class in type_pairs:
        env.register_class(res_name, res_class)


def _get_module_resources(module):
    if callable(getattr(module, 'resource_mapping', None)):
        try:
            return module.resource_mapping().iteritems()
        except Exception as ex:
            LOG.error(_('Failed to load resources from %s') % str(module))
    else:
        return []


def _register_modules(env, modules):
    import itertools

    resource_lists = (_get_module_resources(m) for m in modules)
    _register_resources(env, itertools.chain.from_iterable(resource_lists))


_environment = None


def global_env():
    global _environment
    if _environment is None:
        initialise()
    return _environment


def _list_environment_files(env_dir):
    try:
        return os.listdir(env_dir)
    except OSError as osex:
        LOG.error(_('Failed to read %s') % env_dir)
        LOG.exception(osex)
        return []


def _load_all(env):
    _load_global_resources(env)
    _load_global_environment(env)


def _load_global_environment(env, env_dir=None):
    if env_dir is None:
        cfg.CONF.import_opt('environment_dir', 'heat.common.config')
        env_dir = cfg.CONF.environment_dir

    for env_name in _list_environment_files(env_dir):
        try:
            file_path = os.path.join(env_dir, env_name)
            with open(file_path) as env_fd:
                LOG.info(_('Loading %s') % file_path)
                env_body = environment_format.parse(env_fd.read())
                environment_format.default_for_missing(env_body)
                env.load(env_body)
        except ValueError as vex:
            LOG.error(_('Failed to parse %(dir)s/%(name)s') % {
                      'dir': env_dir, 'name': env_name})
            LOG.exception(vex)
        except IOError as ioex:
            LOG.error(_('Failed to read %(dir)s/%(name)s') % {
                      'dir': env_dir, 'name': env_name})
            LOG.exception(ioex)


def initialise():
    global _environment
    if _environment is not None:
        return

    _environment = environment.Environment({}, user_env=False)
    _load_all(_environment)


def _load_global_resources(env):
    import sys
    from heat.common import plugin_loader

    # load plugin modules
    _register_modules(env, plugin_loader.load_modules(sys.modules[__name__]))

    cfg.CONF.import_opt('plugin_dirs', 'heat.common.config')
    plugin_pkg = plugin_loader.create_subpackage(cfg.CONF.plugin_dirs,
                                                 'heat.engine')
    _register_modules(env, plugin_loader.load_modules(plugin_pkg, True))
