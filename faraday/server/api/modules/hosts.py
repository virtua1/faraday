# Faraday Penetration Test IDE
# Copyright (C) 2016  Infobyte LLC (http://www.infobytesec.com/)
# See the file 'doc/LICENSE' for the license information
from io import StringIO

import logging
import csv
import flask
import re
from flask import Blueprint, make_response, jsonify, abort
import pytz
from flask_classful import route
from marshmallow import fields, Schema
from filteralchemy import Filter, FilterSet, operators
from sqlalchemy import desc
import wtforms
from flask_wtf.csrf import validate_csrf

from faraday.server.utils.database import get_or_create

from faraday.server.api.base import (
    ReadWriteWorkspacedView,
    PaginatedMixin,
    AutoSchema,
    FilterAlchemyMixin,
    FilterSetMeta,
)
from faraday.server.schemas import (
    MetadataSchema,
    MutableField,
    NullToBlankString,
    PrimaryKeyRelatedField,
    SelfNestedField
)
from faraday.server.models import Host, Service, db, Hostname, CommandObject, Command
from faraday.server.api.modules.services import ServiceSchema

host_api = Blueprint('host_api', __name__)

logger = logging.getLogger(__name__)


class HostSchema(AutoSchema):
    _id = fields.Integer(dump_only=True, attribute='id')
    id = fields.Integer()
    _rev = fields.String(default='', dump_only=True)
    ip = fields.String(default='')
    description = fields.String(required=True)  # Explicitly set required=True
    default_gateway = NullToBlankString(
        attribute="default_gateway_ip", required=False)
    name = fields.String(dump_only=True, attribute='ip', default='')
    os = fields.String(default='')
    owned = fields.Boolean(default=False)
    owner = PrimaryKeyRelatedField('username', attribute='creator', dump_only=True)
    services = fields.Integer(attribute='open_service_count', dump_only=True)
    vulns = fields.Integer(attribute='vulnerability_count', dump_only=True)
    credentials = fields.Integer(attribute='credentials_count', dump_only=True)
    hostnames = MutableField(
        PrimaryKeyRelatedField('name', many=True,
                               attribute="hostnames",
                               dump_only=True,
                               default=[]),
        fields.List(fields.String))
    metadata = SelfNestedField(MetadataSchema())
    type = fields.Function(lambda obj: 'Host', dump_only=True)
    service_summaries = fields.Method('get_service_summaries',
                                      dump_only=True)
    versions = fields.Method('get_service_version',
                                      dump_only=True)

    class Meta:
        model = Host
        fields = ('id', '_id', '_rev', 'ip', 'description', 'mac',
                  'credentials', 'default_gateway', 'metadata',
                  'name', 'os', 'owned', 'owner', 'services', 'vulns',
                  'hostnames', 'type', 'service_summaries', 'versions'
                  )

    def get_service_summaries(self, obj):
        return [service.summary
                for service in obj.services
                if service.status == 'open']

    def get_service_version(self, obj):
        return [service.version
                for service in obj.services
                if service.status == 'open']


class ServiceNameFilter(Filter):
    """Filter hosts by service name"""

    def filter(self, query, model, attr, value):
        return query.filter(model.services.any(Service.name == value))


class ServicePortFilter(Filter):
    """Filter hosts by service port"""

    def filter(self, query, model, attr, value):
        try:
            return query.filter(model.services.any(Service.port == int(value)))
        except ValueError:
            return query.filter(None)


class HostFilterSet(FilterSet):
    class Meta(FilterSetMeta):
        model = Host
        fields = ('id', 'ip', 'name', 'os', 'service', 'port')
        operators = (operators.Equal, operators.Like, operators.ILike)
    service = ServiceNameFilter(fields.Str())
    port = ServicePortFilter(fields.Str())


class HostCountSchema(Schema):
    host_id = fields.Integer(dump_only=True, allow_none=False,
                                 attribute='id')
    critical = fields.Integer(dump_only=True, allow_none=False,
                                 attribute='vulnerability_critical_count')
    high = fields.Integer(dump_only=True, allow_none=False,
                              attribute='vulnerability_high_count')
    med = fields.Integer(dump_only=True, allow_none=False,
                              attribute='vulnerability_med_count')
    info = fields.Integer(dump_only=True, allow_none=False,
                              attribute='vulnerability_info_count')
    unclassified = fields.Integer(dump_only=True, allow_none=False,
                              attribute='vulnerability_unclassified_count')
    total = fields.Integer(dump_only=True, allow_none=False,
                                 attribute='vulnerability_total_count')

class HostsView(PaginatedMixin,
                FilterAlchemyMixin,
                ReadWriteWorkspacedView):
    route_base = 'hosts'
    model_class = Host
    order_field = Host.ip.asc()
    schema_class = HostSchema
    filterset_class = HostFilterSet
    get_undefer = [Host.credentials_count,
                   Host.open_service_count,
                   Host.vulnerability_count]
    get_joinedloads = [Host.hostnames, Host.services, Host.update_user]

    @route('/bulk_create/', methods=['POST'])
    def bulk_create(self, workspace_name):
        """
        ---
        post:
          tags: ["Vulns"]
          description: Creates hosts in bulk
          responses:
            201:
              description: Created
              content:
                application/json:
                  schema: HostSchema
            400:
              description: Bad request
            403:
              description: Forbidden
        """
        try:
            validate_csrf(flask.request.form.get('csrf_token'))
        except wtforms.ValidationError:
            flask.abort(403)

        def parse_hosts(list_string):
            items = re.findall(r"([.a-zA-Z0-9_-]+)", list_string)
            return items

        workspace = self._get_workspace(workspace_name)

        logger.info("Create hosts from CSV")
        if 'file' not in flask.request.files:
            abort(400, "Missing File in request")
        hosts_file = flask.request.files['file']
        stream = StringIO(hosts_file.stream.read().decode("utf-8"), newline=None)
        FILE_HEADERS = {'description', 'hostnames', 'ip', 'os'}
        try:
            hosts_reader = csv.DictReader(stream)
            if set(hosts_reader.fieldnames) != FILE_HEADERS:
                logger.error("Missing Required headers in CSV (%s)", FILE_HEADERS)
                abort(400, "Missing Required headers in CSV (%s)" % FILE_HEADERS)
            hosts_created_count = 0
            hosts_with_errors_count = 0
            for host_dict in hosts_reader:
                try:
                    hostnames = parse_hosts(host_dict.pop('hostnames'))
                    other_fields = {'owned': False, 'mac': u'00:00:00:00:00:00', 'default_gateway_ip': u'None'}
                    host_dict.update(other_fields)
                    host = super(HostsView, self)._perform_create(host_dict, workspace_name)
                    host.workspace = workspace
                    for name in hostnames:
                        get_or_create(db.session, Hostname, name=name, host=host, workspace=host.workspace)
                    db.session.commit()
                except Exception as e:
                    logger.error("Error creating host (%s)", e)
                    hosts_with_errors_count += 1
                else:
                    logger.debug("Host Created (%s)", host_dict)
                    hosts_created_count += 1
            return make_response(jsonify(hosts_created=hosts_created_count, hosts_with_errors=hosts_with_errors_count), 200)
        except Exception as e:
            logger.error("Error parsing hosts CSV (%s)", e)
            abort(400, "Error parsing hosts CSV (%s)" % e)


    @route('/<host_id>/services/')
    def service_list(self, workspace_name, host_id):
        services = self._get_object(host_id, workspace_name).services
        return ServiceSchema(many=True).dump(services)

    @route('/countVulns/')
    def count_vulns(self, workspace_name):
        """
        ---
        get:
          tags: ["Hosts"]
          summary: Counts Vulnerabilities per host
          responses:
            200:
              description: Ok
              content:
                application/json:
                  schema: HostCountSchema
        """
        host_ids = flask.request.args.get('hosts', None)
        if host_ids:
            host_id_list = host_ids.split(',')
        else:
            host_id_list = None

        res_dict = {'hosts': {}}

        host_count_schema = HostCountSchema()
        host_count = Host.query_with_count(None, host_id_list, workspace_name)

        for host in host_count.all():
            res_dict["hosts"][host.id] = host_count_schema.dump(host)
        # return counts.data

        return res_dict

    @route('/<host_id>/tools_history/')
    def tool_impacted_by_host(self, workspace_name, host_id):
        workspace = self._get_workspace(workspace_name)
        query = db.session.query(Host, Command).filter(Host.id == CommandObject.object_id,
                                                       CommandObject.object_type == 'host',
                                                       Command.id == CommandObject.command_id,
                                                       Host.workspace_id == workspace.id,
                                                       Host.id == host_id).order_by(desc(CommandObject.create_date))
        result = query.all()
        res_dict = {'tools': []}
        for row in result:
            _, command = row
            res_dict['tools'].append({'command': command.tool, 'user': command.user, 'params': command.params, 'command_id': command.id, 'create_date': command.create_date.replace(tzinfo=pytz.utc).strftime("%c")})
        return res_dict

    def _perform_create(self, data, **kwargs):
        hostnames = data.pop('hostnames', [])
        host = super(HostsView, self)._perform_create(data, **kwargs)
        for name in hostnames:
            get_or_create(db.session, Hostname, name=name, host=host,
                          workspace=host.workspace)
        db.session.commit()
        return host

    def _update_object(self, obj, data):
        try:
            hostnames = data.pop('hostnames')
        except KeyError:
            pass
        else:
            obj.set_hostnames(hostnames)

        # A commit is required here, otherwise it breaks (i'm not sure why)
        db.session.commit()

        return super(HostsView, self)._update_object(obj, data)

    def _filter_query(self, query):
        query = super(HostsView, self)._filter_query(query)
        search_term = flask.request.args.get('search', None)
        if search_term is not None:
            like_term = '%' + search_term + '%'
            match_ip = Host.ip.ilike(like_term)
            match_service_name = Host.services.any(
                Service.name.ilike(like_term))
            match_os = Host.os.ilike(like_term)
            match_hostname = Host.hostnames.any(Hostname.name.ilike(like_term))
            query = query.filter(match_ip |
                                 match_service_name |
                                 match_os |
                                 match_hostname)
        return query

    def _envelope_list(self, objects, pagination_metadata=None):
        hosts = []
        for host in objects:
            hosts.append({
                'id': host['id'],
                'key': host['id'],
                'value': host
            })
        return {
            'rows': hosts,
            'total_rows': (pagination_metadata and pagination_metadata.total
                           or len(hosts)),
        }

    @route('bulk_delete/', methods=['DELETE'])
    def bulk_delete(self, workspace_name):
        workspace = self._get_workspace(workspace_name)
        json_request = flask.request.get_json()
        if not json_request:
            flask.abort(400, 'Invalid request. Check the request data or the content type of the request')
        hosts_ids = json_request.get('hosts_ids', [])
        hosts_ids = [host_id for host_id in hosts_ids if isinstance(host_id, int)]
        deleted_hosts = 0
        if hosts_ids:
            deleted_hosts = Host.query.filter(
                Host.id.in_(hosts_ids),
                Host.workspace_id == workspace.id).delete(synchronize_session='fetch')
        else:
            flask.abort(400, "Invalid request")

        db.session.commit()
        response = {'deleted_hosts': deleted_hosts}
        return flask.jsonify(response)


HostsView.register(host_api)
# I'm Py3
