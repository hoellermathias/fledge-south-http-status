# -*- coding: utf-8 -*-

# FLEDGE_BEGIN
# See: http://fledge-iot.readthedocs.io/
# FLEDGE_END

""" Weather report from OpenWeatherMap async plugin """

import copy
import asyncio
import json
import logging
from threading import Thread
from aiohttp import web

from fledge.common import logger
from fledge.plugins.common import utils
import async_ingest
import pycurl


__author__ = "Mark Riddoch, Ashwin Gopalakrishnan, Amarendra K Sinha"
__copyright__ = "Copyright (c) 2018 Dianomic Systems"
__license__ = "Apache 2.0"
__version__ = "${VERSION}"

_DEFAULT_CONFIG = {
    'plugin': {
        'description': 'HTTP Status check',
        'type': 'string',
        'default': 'http-status',
        'readonly': 'true'
    },
    'url': {
        'description': 'API URL to fetch information',
        'type': 'string',
        'default': 'https://www.univie.ac.at/',
        'order': '1',
        'displayName': 'API URL',
        'mandatory':  'true'
    },
    'assetName': {
        'description': 'Asset Name',
        'type': 'string',
        'default': 'http-status',
        'order': '2',
        'displayName': 'Asset Name',
        'mandatory':  'true'
    },
    'rate': {
        'description': 'Rate at which to send requests in seconds',
        'type': 'integer',
        'default': '10',
        'minimum': '1',
        'order': '3',
        'displayName': 'Request Interval'
    },
    'pkiFile': {
        'description': 'Path to the p12 certificate file. (OPTIONAL)',
        'type': 'string',
        'order': '4',
        'default': '',
        'displayName': 'Certificate P12 file'
    },
    'pkiPasswd': {
        'description': 'Password for the certificate (OPTIONAL)',
        'type': 'string',
        'default': '',
        'order': '5',
        'displayName': 'Cert Password'
    }
}
_LOGGER = logger.setup(__name__, level=logging.INFO)

c_callback = None
c_ingest_ref = None
loop = None
t = None
task = None


def plugin_info():
    """ Returns information about the plugin.
    Args:
    Returns:
        dict: plugin information
    Raises:
    """

    return {
        'name': 'HTTP Status',
        'version': '1.9.1',
        'mode': 'async',
        'type': 'south',
        'interface': '1.0',
        'config': _DEFAULT_CONFIG
    }


def plugin_init(config):
    """ Initialise the plugin with WeatherReport class' object that will periodically fetch weather data
        Args:
           config: JSON configuration document for the South plugin configuration category
        Returns:
           data: JSON object to be used in future calls to the plugin
        Raises:
    """
    data = copy.deepcopy(config)
    return data


def plugin_start(handle):
    global loop, t, task
    loop = asyncio.new_event_loop()
    try:
        url = handle['url']['value']
        rate = handle['rate']['value']
        asset_name = handle['assetName']['value']
        cert_file = handle['pkiFile']['value']
        cert_pwd = handle['pkiPasswd']['value']
        task = WeatherReport(url, rate, asset_name, cert_file, cert_pwd)
        task.start()

        def run():
            global loop
            loop.run_forever()

        t = Thread(target=run)
        t.start()
    except Exception as e:
        _LOGGER.exception("OpenWeatherMap plugin failed to start. Details %s", str(e))
        raise


def plugin_reconfigure(handle, new_config):
    """ Reconfigures the plugin

    it should be called when the configuration of the plugin is changed during the operation of the south service.
    The new configuration category should be passed.

    Args:
        handle: handle returned by the plugin initialisation call
        new_config: JSON object representing the new configuration category for the category
    Returns:
        new_handle: new handle to be used in the future calls
    Raises:
    """
    _LOGGER.info("Old config for OpenWeatherMap plugin {} \n new config {}".format(handle, new_config))

    plugin_shutdown(handle)
    new_handle = plugin_init(new_config)
    plugin_start(new_handle)
    return new_handle


def plugin_shutdown(handle):
    try:
        _LOGGER.info('South http-status plugin shutting down.')
        task.stop()
        loop.stop()
    except Exception as e:
        _LOGGER.exception(str(e))
        raise


def plugin_register_ingest(handle, callback, ingest_ref):
    """Required plugin interface component to communicate to South C server

    Args:
        handle: handle returned by the plugin initialisation call
        callback: C opaque object required to passed back to C->ingest method
        ingest_ref: C opaque object required to passed back to C->ingest method
    """
    global c_callback, c_ingest_ref
    c_callback = callback
    c_ingest_ref = ingest_ref
    _LOGGER.debug(f': register ingest: {callback}, {ingest_ref}')


class WeatherReport(object):
    """ Handle integration with OpenWeatherMap API """

    __slots__ = ['_interval', 'url', 'asset_name', '_handler', 'cert_file', 'cert_pwd']

    def __init__(self, url, rate, asset_name, cert_file, cert_pwd):
        self._interval = float(rate)
        self.url = url
        self.asset_name = asset_name
        self.cert_file = cert_file
        self.cert_pwd = cert_pwd
        self._handler = None
        _LOGGER.debug(": init----")

    def _run(self):
        _LOGGER.debug(f'run {self.url}')
        self.fetch()
        _LOGGER.debug('run fetch end')
        self._handler = loop.call_later(self._interval, self._run)

    def start(self):
        _LOGGER.debug('start')
        self._handler = loop.call_later(self._interval, self._run)

    def stop(self):
        self._handler.cancel()

    def fetch(self):
        try:
            err = ''
            c = pycurl.Curl()
            try:
                c.setopt(c.URL, self.url)
                if self.cert_file and self.cert_pwd:
                    c.setopt(pycurl.SSLCERTTYPE, 'P12')
                    c.setopt(pycurl.KEYPASSWD, self.cert_pwd)
                    c.setopt(pycurl.SSLCERT, self.cert_file)
                r = c.perform() 
            except Exception as ex:
                status = 999
                time = 0
                err = str(ex)
            else:
                status = r.getinfo(c.HTTP_CODE)
                time = r.getinfo(c.TOTAL_TIME)
                err = ""

            data = {
                'asset': self.asset_name,
                'timestamp': utils.local_timestamp(),
                'readings': [{'status': status,
                              'time': time,
                              'error': err,
                              'url': self.url}]
            }
            async_ingest.ingest_callback(c_callback, c_ingest_ref, data)
            _LOGGER.debug(f'status: ----{status}')
        except Exception as ex:
            err = "Unable to fetch information from api.openweathermap: {}".format(str(ex))
            _LOGGER.error(err)
