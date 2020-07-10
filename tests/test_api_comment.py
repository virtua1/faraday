'''
Faraday Penetration Test IDE
Copyright (C) 2013  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information

'''
from __future__ import absolute_import

from faraday.server.api.modules.comments import CommentView
from faraday.server.models import Comment
from tests.factories import ServiceFactory
from tests.test_api_workspaced_base import ReadOnlyAPITests
from tests import factories


class TestCredentialsAPIGeneric(ReadOnlyAPITests):
    model = Comment
    factory = factories.CommentFactory
    view_class = CommentView
    api_endpoint = 'comment'
    update_fields = ['username', 'password']

    def _create_raw_comment(self, object_type, object_id):
        return {
            'object_id': object_id,
            'object_type': object_type,
            'description': '',
            'metadata': {
                'command_id': '',
                'create_time': 1513093980.157945,
                'creator': 'Nmap',
                'owner': '',
                'update_action': 0,
                'update_controller_action': 'No model controller call',
                'update_time': 1513093980.157948,
                'update_user': ''
            },
            'name': 'website',
            'owned': False,
            'owner': '',
            'text': '',
            'type': 'Note'
        }

    def test_create_comment_from_plugins(self, test_client, session):
        service = ServiceFactory.create(workspace=self.workspace)
        session.commit()
        initial_comment_count = len(session.query(Comment).all())
        raw_comment = self._create_raw_comment('service', service.id)
        res = test_client.post(self.url(workspace=self.workspace), data=raw_comment)
        assert res.status_code == 201
        assert len(session.query(Comment).all()) == initial_comment_count + 1

    def test_cannot_create_comment__with_invalid_object_type(self, test_client, session):
        service = ServiceFactory.create(workspace=self.workspace)
        session.commit()
        raw_comment = self._create_raw_comment('workspace', service.id)
        res = test_client.post(self.url(), data=raw_comment)
        assert res.status_code == 400
        assert 'Must be one of' in res.json['messages']['json']['object_type'][0]

    def test_cannot_create_comment_of_another_workspace_object(self, test_client, session, second_workspace):
        service = ServiceFactory.create(workspace=self.workspace)
        session.commit()
        raw_comment = self._create_raw_comment('service', service.id)
        res = test_client.post(self.url(workspace=second_workspace), data=raw_comment)
        assert res.status_code == 400
        assert res.json == {u'message': u"Can't comment object of another workspace"}

    def test_cannot_create_comment_of_inexistent_object(self, test_client, session):
        raw_comment = self._create_raw_comment('service', 456464556)
        res = test_client.post(self.url(workspace=self.workspace), data=raw_comment)
        assert res.status_code == 400
        assert res.json == {u'message': u"Can't comment inexistent object"}


    def test_create_unique_comment_for_plugins(self, session, test_client):
        """


        """
        service = ServiceFactory.create(workspace=self.workspace)
        session.commit()
        initial_comment_count = len(session.query(Comment).all())
        raw_comment = self._create_raw_comment('service', service.id)
        res = test_client.post(self.url(workspace=self.workspace),
                               data=raw_comment)
        assert res.status_code == 201
        assert len(session.query(Comment).all()) == initial_comment_count + 1

        url = self.url(workspace=self.workspace).strip('/') + '_unique/'
        res = test_client.post(url, data=raw_comment)
        assert res.status_code == 409
        assert 'object' in res.json
        assert type(res.json) == dict

    def test_create_unique_comment_for_plugins_after_and_before(self, session, test_client):
        """


        """
        service = ServiceFactory.create(workspace=self.workspace)
        session.commit()
        initial_comment_count = len(session.query(Comment).all())
        raw_comment = self._create_raw_comment('service', service.id)
        url = self.url(workspace=self.workspace).strip('/') + '_unique/'
        res = test_client.post(url,
                               data=raw_comment)
        assert res.status_code == 201
        assert len(session.query(Comment).all()) == initial_comment_count + 1

        res = test_client.post(url, data=raw_comment)
        assert res.status_code == 409
        assert 'object' in res.json
        assert type(res.json) == dict


# I'm Py3
