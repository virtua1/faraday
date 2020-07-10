'''
Faraday Penetration Test IDE
Copyright (C) 2013  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information

'''
from __future__ import absolute_import

import os
import pytest
from io import BytesIO

from tests.factories import WorkspaceFactory

from faraday.server.threads.reports_processor import REPORTS_QUEUE

from faraday.server.models import Host, Vulnerability, Service, Command


@pytest.mark.usefixtures('logged_user')
class TestFileUpload():

    def test_file_upload(self, test_client, session, csrf_token, logged_user):
        ws = WorkspaceFactory.create(name="abc")
        session.add(ws)
        session.commit()
        path = os.path.join(
                os.path.dirname(os.path.realpath(__file__)),
                'data',
                'nmap_plugin_with_api.xml')

        with open(path,'rb') as report:
            file_contents = report.read()
        data = {
            'file' : (BytesIO(file_contents), 'nmap_report.xml'),
            'csrf_token' : csrf_token
        }

        res = test_client.post(
                '/v2/ws/{ws_name}/upload_report'.format(ws_name=ws.name),
                data=data,
                use_json_data=False)

        assert res.status_code == 200
        assert len(REPORTS_QUEUE.queue) == 1
        queue_elem = REPORTS_QUEUE.queue[0]
        assert queue_elem[0] == ws.name
        assert queue_elem[2].id == logged_user.id

        # I'm testing a method which lost referene of workspace and logged_user within the test
        ws_id = ws.id
        logged_user_id = logged_user.id

        from faraday.server.threads.reports_processor import ReportsManager
        false_thread = ReportsManager(None)
        false_thread.process_report(queue_elem[0], queue_elem[1], queue_elem[2])
        command = Command.query.filter(Command.workspace_id == ws_id).one()
        assert command
        assert command.creator_id == logged_user_id
        host = Host.query.filter(Host.workspace_id == ws_id).first()
        assert host
        assert host.creator_id == logged_user_id
        service = Service.query.filter(Service.workspace_id == ws_id).first()
        assert service
        assert service.creator_id == logged_user_id


    def test_no_file_in_request(self, test_client, session):
        ws = WorkspaceFactory.create(name="abc")
        session.add(ws)
        session.commit()

        res = test_client.post(
                '/v2/ws/{ws_name}/upload_report'.format(ws_name=ws.name))

        assert res.status_code == 400


    def test_request_without_csrf_token(self, test_client, session):
        ws = WorkspaceFactory.create(name="abc")
        session.add(ws)
        session.commit()
        path = os.path.join(
                os.path.dirname(os.path.realpath(__file__)),
                'data',
                'nmap_plugin_with_api.xml')

        with open(path,'r') as report:
            file_contents = report.read().encode('utf-8')

        data = {
            'file' : (BytesIO(file_contents), 'nmap_report.xml'),
        }

        res = test_client.post(
                '/v2/ws/{ws_name}/upload_report'.format(ws_name=ws.name),
                data=data,
                use_json_data=False)

        assert res.status_code == 403
    

    def test_request_with_workspace_deactivate(self, test_client, session, csrf_token):
        ws = WorkspaceFactory.create(name="abc")
        ws.active = False
        session.add(ws)
        session.commit()
        path = os.path.join(
                os.path.dirname(os.path.realpath(__file__)),
                'data',
                'nmap_plugin_with_api.xml')

        with open(path,'r') as report:
            file_contents = report.read().encode('utf-8')

        data = {
            'file' : (BytesIO(file_contents), 'nmap_report.xml'),
            'csrf_token' : csrf_token
        }
        res = test_client.post(
                '/v2/ws/{ws_name}/upload_report'.format(ws_name=ws.name),
                data=data,
                use_json_data=False)

        assert res.status_code == 404
