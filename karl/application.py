import logging
import os
import sys
import transaction
import webob

from zope.component import queryUtility

from pyramid_zcml import make_app as bfg_make_app
from pyramid.scripting import get_root
from pyramid.traversal import resource_path
from repoze.who.plugins.zodb.users import Users
from repoze.zodbconn.finder import PersistentApplicationFinder

from karl.log import configure_log
from karl.log import get_logger
from karl.log import set_subsystem
from karl.views.utils import get_user_home
from karl.utils import asbool
from karl.bootstrap.bootstrap import populate
from karl.bootstrap.interfaces import IBootstrapper

def appmaker(root):
    bootstrapper = queryUtility(IBootstrapper, default=populate)
    if not root.has_key('site'):
        bootstrapper(root)
        transaction.commit()
    return root['site']

def make_app(global_config, **kw):
    config = global_config.copy()
    config.update(kw)

    # paster app config callback
    zodb_uri = config.get('zodb_uri')
    if zodb_uri is None:
        raise ValueError('zodb_uri must not be None')
    get_root = PersistentApplicationFinder(zodb_uri, appmaker)

    # Coerce a value out of the [app:karl] section in the INI file
    jquery_dev_mode = config.get('jquery_dev_mode', False)
    config['jquery_dev_mode'] = asbool(jquery_dev_mode)
    config['read_only'] = asbool(config.get('read_only', False))

    # Set up logging
    configure_log(**config)
    set_subsystem('karl')

    # Set up logging admin view (coerce instances to list)
    if 'logs_view' in config:
        config['logs_view'] = map(os.path.abspath, config['logs_view'].split())

    for key in ('syslog_view_instances', 'error_monitor_subsystems'):
        if key in config:
            config[key] = config[key].split()

    # Make BFG app
    pkg_name = config.get('package', None)
    if pkg_name is not None:
        __import__(pkg_name)
        package = sys.modules[pkg_name]
        app = bfg_make_app(get_root, package, options=config)
    else:
        filename = 'karl.includes:standalone.zcml'
        app = bfg_make_app(get_root, filename=filename, options=config)

    return app


def find_users(root):
    # Called by repoze.who
    if not 'site' in root:
        return Users()
    return root['site'].users


def unconditional_veto(environ, status, headers):
    """
    Can be used in read-only mode to avoid attempting to commit any
    transactions.
    """
    return True
