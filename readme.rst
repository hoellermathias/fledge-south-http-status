****************************
Fledge South HTTP STATUS
****************************

This South service plugin is based on the Fledge South OpenWeather plugin.
This directory contains a South service plugin that sends HTTP requests on a regular (configured default to 10 seconds) interval.

Installation 
-------------

0. Install ``sudo apt-get install libssl-dev`` (command for debian systems; google for other distributions)
1. Install requests: run ``python3 -m pip install -r requirements.txt``
2. copy ``http-status`` directory to ``FLEDGE_HOME_DIR/python/fledge/plugins/south/``
3. Test the installation by sending a GET request to ``http://FLEDGE_HOME_URL/fledge/plugins/installed?type=south``. The response is a JSON listing all installed north plugins and should look like: ``{"plugins": [{"name": "http-status", "type": "south", "description": "HTTP Status Plugin", "version": "1.0", "installedDirectory": "south/http-status", "packageName": "fledge-south-http-status"}, ...]}``


