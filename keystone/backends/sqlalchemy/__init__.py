# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 OpenStack LLC.
# All Rights Reserved.
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

import ast
import logging
import time

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError, DBAPIError
from sqlalchemy.orm import joinedload, aliased, sessionmaker
from sqlalchemy.pool import StaticPool

from keystone.common import config
from keystone.backends.sqlalchemy import models
import keystone.utils as utils
import keystone.backends.api as top_api
import keystone.backends.models as top_models
_ENGINE = None
_MAKER = None
_MAX_RETRIES = None
_RETRY_INTERVAL = None
logger = None
BASE = models.Base

MODEL_PREFIX = 'keystone.backends.sqlalchemy.models.'
API_PREFIX = 'keystone.backends.sqlalchemy.api.'
FOR_TESTING_ONLY = 'for_testing_only'


def configure_backend(options):
    """
    Establish the database, create an engine if needed, and
    register the models.

    :param options: Mapping of configuration options
    """
    global _ENGINE
    global _MAX_RETRIES
    global _RETRY_INTERVAL
    global logger
    if not _ENGINE:
        debug = config.get_option(
            options, 'debug', type='bool', default=False)
        verbose = config.get_option(
            options, 'verbose', type='bool', default=False)
        timeout = config.get_option(
            options, 'sql_idle_timeout', type='int', default=3600)
        _MAX_RETRIES = config.get_option(
            options, 'sql_max_retries', type='int', default=10)
        _RETRY_INTERVAL = config.get_option(
            options, 'sql_retry_interval', type='int', default=1)
        if options['sql_connection'] == FOR_TESTING_ONLY:
            _ENGINE = create_engine('sqlite://',
                connect_args={'check_same_thread': False},
                poolclass=StaticPool)
        else:
            _ENGINE = create_engine(options['sql_connection'],
                pool_recycle=timeout)
            _ENGINE.create = wrap_db_error(_ENGINE.create)

        logger = logging.getLogger('sqlalchemy.engine')
        if debug:
            logger.setLevel(logging.DEBUG)
        elif verbose:
            logger.setLevel(logging.INFO)

        register_models(options)

        # this is TERRIBLE coupling, but...
        # if we're starting up a test database, load sample fixtures
        if options['sql_connection'] == FOR_TESTING_ONLY:
            from keystone.test import sampledata
            sampledata.load_fixture()


def get_session(autocommit=True, expire_on_commit=False):
    """Helper method to grab session"""
    global _MAKER, _ENGINE
    if not _MAKER:
        assert _ENGINE
        _MAKER = sessionmaker(bind=_ENGINE,
                              autocommit=autocommit,
                              expire_on_commit=expire_on_commit)
    session = _MAKER()
    session.query = wrap_db_error(session.query)
    session.flush = wrap_db_error(session.flush)
    session.execute = wrap_db_error(session.execute)
    session.begin = wrap_db_error(session.begin)
    return session


def is_db_connection_error(args):
    """Return True if error in connecting to db."""
    conn_err_codes = ('2002', '2006')
    for err_code in conn_err_codes:
        if args.find(err_code) != -1:
            return True
    return False


def wrap_db_error(f):
    """Retry DB connection. Copied from nova and modified."""
    def _wrap(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except OperationalError, e:
            if not is_db_connection_error(e.args[0]):
                raise

            global _MAX_RETRIES
            global _RETRY_INTERVAL
            remaining_attempts = _MAX_RETRIES
            while True:
                logger.warning(_('SQL connection failed. %d attempts left.'),
                                remaining_attempts)
                remaining_attempts -= 1
                time.sleep(_RETRY_INTERVAL)
                try:
                    return f(*args, **kwargs)
                except OperationalError, e:
                    if remaining_attempts == 0 or \
                       not is_db_connection_error(e.args[0]):
                        raise
                except DBAPIError:
                    raise
        except DBAPIError:
            raise
    _wrap.func_name = f.func_name
    return _wrap


def register_models(options):
    """Register Models and create properties"""
    global _ENGINE
    assert _ENGINE
    # Need to decide.Not This is missing
    # and prevents foreign key reference checks.
    # _ENGINE.execute('pragma foreign_keys=on')
    supported_alchemy_models = ast.literal_eval(
                    options["backend_entities"])
    supported_alchemy_tables = []
    for supported_alchemy_model in supported_alchemy_models:
        model = utils.import_module(MODEL_PREFIX + supported_alchemy_model)
        supported_alchemy_tables.append(model.__table__)
        top_models.set_value(supported_alchemy_model, model)
        if model.__api__ != None:
            model_api = utils.import_module(API_PREFIX + model.__api__)
            top_api.set_value(model.__api__, model_api.get())
    creation_tables = []
    for table in reversed(BASE.metadata.sorted_tables):
        if table in supported_alchemy_tables:
            creation_tables.append(table)
    BASE.metadata.create_all(_ENGINE, tables=creation_tables, checkfirst=True)


def unregister_models():
    """Unregister Models, useful clearing out data before testing"""
    global _ENGINE
    assert _ENGINE
    BASE.metadata.drop_all(_ENGINE)
