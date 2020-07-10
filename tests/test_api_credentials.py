'''
Faraday Penetration Test IDE
Copyright (C) 2013  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information

'''
from __future__ import absolute_import

import pytest

from tests import factories
from tests.test_api_workspaced_base import (
    ReadWriteAPITests,
)
from faraday.server.api.modules.credentials import CredentialView
from faraday.server.models import Credential
from tests.factories import HostFactory, ServiceFactory


class TestCredentialsAPIGeneric(ReadWriteAPITests):
    model = Credential
    factory = factories.CredentialFactory
    view_class = CredentialView
    api_endpoint = 'credential'
    update_fields = ['username', 'password']

    def test_get_list_backwards_compatibility(self, test_client, session, second_workspace):
        cred = self.factory.create(workspace=second_workspace)
        session.add(cred)
        session.commit()
        res = test_client.get(self.url())
        assert res.status_code == 200
        assert 'rows' in res.json
        for vuln in res.json['rows']:
            assert set([u'_id', u'id', u'key', u'value']) == set(vuln.keys())
            object_properties = [
                u'_id',
                u'couchdbid',
                u'description',
                u'metadata',
                u'name',
                u'owner',
                u'password',
                u'username',
                u'host_ip',
                u'service_name',
                u'target'
            ]
            expected = set(object_properties)
            result = set(vuln['value'].keys())
            assert expected - result == set()

    def test_create_from_raw_data_host_as_parent(self, session, test_client,
                                                 workspace, host_factory):
        host = host_factory.create(workspace=workspace)
        session.commit()
        raw_data = {
            "_id":"1.e5069bb0718aa519852e6449448eedd717f1b90d",
            "name":"name",
            "username":"username",
            "metadata":{"update_time":1508794240799,"update_user":"",
                        "update_action":0,"creator":"UI Web",
                        "create_time":1508794240799,"update_controller_action":"",
                        "owner":""},
            "password":"pass",
            "type":"Cred",
            "owner":"",
            "description":"",
            "parent": host.id,
            "parent_type": "Host"
        }
        res = test_client.post(self.url(), data=raw_data)
        assert res.status_code == 201
        assert res.json['host_ip'] == host.ip
        assert res.json['service_name'] is None
        assert res.json['target'] == host.ip

    def test_create_from_raw_data_service_as_parent(
            self, session, test_client, workspace, service_factory):
        service = service_factory.create(workspace=workspace)
        session.commit()
        raw_data = {
            "_id":"1.e5069bb0718aa519852e6449448eedd717f1b90d",
            "name":"name",
            "username":"username",
            "metadata":{"update_time":1508794240799,"update_user":"",
                        "update_action":0,"creator":"UI Web",
                        "create_time":1508794240799,"update_controller_action":"",
                        "owner":""},
            "password":"pass",
            "type":"Cred",
            "owner":"",
            "description":"",
            "parent": service.id,
            "parent_type": "Service"
        }
        res = test_client.post(self.url(), data=raw_data)
        assert res.status_code == 201
        assert res.json['host_ip'] is None
        assert res.json['service_name'] == service.name
        assert res.json['target'] == service.host.ip + '/' + service.name

    def test_get_credentials_for_a_host_backwards_compatibility(
            self, session, test_client, host):
        credential = self.factory.create(host=host, service=None,
                                         workspace=self.workspace)
        session.commit()
        res = test_client.get(self.url(workspace=credential.workspace) + '?host_id={0}'.format(credential.host.id))
        assert res.status_code == 200
        assert [cred['value']['parent'] for cred in res.json['rows']] == [credential.host.id]
        assert [cred['value']['parent_type'] for cred in res.json['rows']] == [u'Host']

    def test_get_credentials_for_a_service_backwards_compatibility(self, session, test_client):
        service = ServiceFactory.create()
        credential = self.factory.create(service=service, host=None, workspace=service.workspace)
        session.commit()
        res = test_client.get(self.url(workspace=credential.workspace) + '?service={0}'.format(credential.service.id))
        assert res.status_code == 200
        assert [cred['value']['parent'] for cred in res.json['rows']] == [credential.service.id]
        assert [cred['value']['parent_type'] for cred in res.json['rows']] == [u'Service']

    def _generate_raw_update_data(self, name, username, password, parent_id):
        return {
            "id": 7,
            "name": name,
            "username": username,
            "metadata": {"update_time": 1508960699994, "create_time": 1508965372,
                         "update_user": "", "update_action": 0, "creator": "Metasploit", "owner": "",
                         "update_controller_action": "No model controller call",
                         "command_id": "e1a042dd0e054c1495e1c01ced856438"},
            "password": password,
            "type": "Cred",
            "parent_type": "Host",
            "parent": parent_id,
            "owner": "",
            "description": "",
            "_rev": ""}

    def test_update_credentials_with_invalid_parent(self, test_client, session):
        credential = self.factory.create()
        session.add(credential)
        session.commit()

        raw_data = self._generate_raw_update_data('Name1', 'Username2', 'Password3', parent_id=43)

        res = test_client.put(self.url(workspace=credential.workspace) + str(credential.id) + '/', data=raw_data)
        assert res.status_code == 400

    def test_create_with_invalid_parent_type(
            self, session, test_client, workspace, service_factory):
        service = service_factory.create(workspace=workspace)
        session.commit()
        raw_data = {
            "_id":"1.e5069bb0718aa519852e6449448eedd717f1b90d",
            "name":"name",
            "username":"username",
            "metadata":{"update_time":1508794240799,"update_user":"",
                        "update_action":0,"creator":"UI Web",
                        "create_time":1508794240799,"update_controller_action":"",
                        "owner":""},
            "password":"pass",
            "type":"Cred",
            "owner":"",
            "description":"",
            "parent": service.id,
            "parent_type": "Vulnerability"
        }
        res = test_client.post(self.url(), data=raw_data)
        assert res.status_code == 400
        assert res.json['messages']['json']['_schema'] == ['Unknown parent type: Vulnerability']


    def test_update_credentials(self, test_client, session, host):
        credential = self.factory.create(host=host, service=None,
                                         workspace=self.workspace)
        session.commit()

        raw_data = self._generate_raw_update_data(
            'Name1', 'Username2', 'Password3', parent_id=credential.host.id)

        res = test_client.put(self.url(workspace=credential.workspace) + str(credential.id) + '/', data=raw_data)
        assert res.status_code == 200
        assert res.json['username'] == u'Username2'
        assert res.json['password'] == u'Password3'
        assert res.json['name'] == u'Name1'

    @pytest.mark.parametrize("parent_type, parent_factory", [
        ("Host", HostFactory),
        ("Service", ServiceFactory),
    ], ids=["with host parent", "with service parent"])
    def test_create_with_parent_of_other_workspace(
            self, parent_type, parent_factory, test_client, session,
            second_workspace):
        parent = parent_factory.create(workspace=second_workspace)
        session.commit()
        assert parent.workspace_id != self.workspace.id
        data = {
            "username": "admin",
            "password": "admin",
            "name": "test",
            "parent_type": parent_type,
            "parent": parent.id
        }
        res = test_client.post(self.url(), data=data)
        assert res.status_code == 400
        assert b'Parent id not found' in res.data

    @pytest.mark.parametrize("parent_type, parent_factory", [
        ("Host", HostFactory),
        ("Service", ServiceFactory),
    ], ids=["with host parent", "with service parent"])
    def test_update_with_parent_of_other_workspace(
            self, parent_type, parent_factory, test_client, session,
            second_workspace, credential_factory):
        parent = parent_factory.create(workspace=second_workspace)
        if parent_type == 'Host':
            credential = credential_factory.create(
                host=HostFactory.create(workspace=self.workspace),
                service=None,
                workspace=self.workspace)
        else:
            credential = credential_factory.create(
                host=None,
                service=ServiceFactory.create(workspace=self.workspace),
                workspace=self.workspace)
        session.commit()
        assert parent.workspace_id != self.workspace.id
        data = {
            "username": "admin",
            "password": "admin",
            "name": "test",
            "parent_type": parent_type,
            "parent": parent.id
        }
        res = test_client.put(self.url(credential), data=data)
        assert res.status_code == 400
        assert b'Parent id not found' in res.data


    def test_sort_credentials_target(self, test_client, second_workspace):
        host = HostFactory(workspace=second_workspace, ip="192.168.1.1")
        service = ServiceFactory(name="http", workspace=second_workspace, host=host)

        host2 = HostFactory(workspace=second_workspace, ip="192.168.1.2")
        service2 = ServiceFactory(name="ssh", workspace=second_workspace, host=host2)

        credential = self.factory.create(service=service, host=None, workspace=second_workspace)
        credential2 = self.factory.create(service=None, host=host2, workspace=second_workspace)
        credential3 = self.factory.create(service=None, host=host, workspace=second_workspace)
        credential4 = self.factory.create(service=service2, host=None, workspace=second_workspace)

        credentials_target = [
            "{}/{}".format(credential.service.host.ip, credential.service.name),
            "{}".format(credential2.host.ip),
            "{}".format(credential3.host.ip),
            "{}/{}".format(credential4.service.host.ip, credential4.service.name),
        ]

        # Desc order
        response = test_client.get(self.url(workspace=second_workspace) + "?sort=target&sort_dir=desc")
        assert response.status_code == 200
        assert sorted(credentials_target, reverse=True) == [ v['value']['target'] for v in response.json['rows']]

        # Asc order
        response = test_client.get(self.url(workspace=second_workspace) + "?sort=target&sort_dir=asc")
        assert response.status_code == 200
        assert sorted(credentials_target) == [v['value']['target'] for v in response.json['rows']]
# I'm Py3
