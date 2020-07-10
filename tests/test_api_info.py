'''
Faraday Penetration Test IDE
Copyright (C) 2013  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information

'''
from __future__ import absolute_import

import os
import pytest


@pytest.mark.usefixtures('logged_user')
class TestAPIInfoEndpoint:

    def test_api_info(self, test_client):
        current_dir = os.getcwd()
        # this is a bug on the info api!
        # we require faraday to be a package since we can't import
        # from base path when our current working dir is tests.
        if 'tests' in current_dir:
            faraday_base = os.path.join(current_dir, '..')
            os.chdir(faraday_base)

        response = test_client.get('v2/info')
        assert response.status_code == 200
        assert response.json['Faraday Server'] == 'Running'
        # to avoid side effects
        os.chdir(current_dir)

    def test_get_config(self, test_client):
        res = test_client.get('/config')
        assert res.status_code == 200
        assert res.json['lic_db'] == 'faraday_licenses'
