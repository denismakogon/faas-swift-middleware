# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json

from swift.common.http import is_success
from swift.common.swob import Request
from swift.common.utils import split_path, get_logger
from swift.common.request_helper import get_sys_meta_prefix
from swift.proxy.controllers.base import get_container_info

from eventlet import Timeout
import six
if six.PY3:
    from eventlet.green.urllib import request as urllib2
else:
    from eventlet.green import urllib2

# x-container-sysmeta-webhook
SYSMETA_WEBHOOK = get_sys_meta_prefix('container') + 'webhook'


# Based on http://docs.openstack.org/developer/swift/development_middleware.html
class FunctionsWebhookMiddleware(object):

    def __init__(self, app, conf):
        self.app = app
        self.logger = get_logger(conf, log_route='functions_webhook')

    def __call__(self, env, start_response):
        req = Request(env)
        obj = None
        try:
            version, account, container, obj = split_path(req.path_info, 4, 4, True)
        except ValueError:
            # not an object request
            pass

        if 'x-webhook' in req.headers:
            # translate user's request header to sysmeta
            req.headers[SYSMETA_WEBHOOK] = req.headers['x-webhook']

        if 'x-remove-webhook' in req.headers:
            # empty value will tombstone sysmeta
            req.headers[SYSMETA_WEBHOOK] = ''

        # account and object storage will ignore x-container-sysmeta-*
        resp = req.get_response(self.app)
        if obj and is_success(resp.status_int) and req.method == 'PUT':
            container_info = get_container_info(req.environ, self.app)
            # container_info may have our new sysmeta key
            webhook = container_info['sysmeta'].get('webhook')
            if webhook:
                # create a POST request with obj name as body
                webhook_req = urllib2.Request(webhook, data=json.dumps({
                    "x-auth-token": req.headers.get("X-Auth-Token"),
                    "version": version,
                    "account": account,
                    "container": container,
                    "object": obj,
                    "project_id": account[account.index('_') + 1:],
                }))
                with Timeout(60):
                    try:
                        urllib2.urlopen(webhook_req).read()
                    except (Exception, Timeout):
                        self.logger.exception(
                            'failed POST to webhook %s' % webhook)
                    else:
                        self.logger.info(
                            'successfully called webhook %s' % webhook)
        if 'x-container-sysmeta-webhook' in resp.headers:
            # translate sysmeta from the backend resp to
            # user-visible client resp header
            resp.headers['x-webhook'] = resp.headers[SYSMETA_WEBHOOK]
        return resp


def webhook_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def webhook_filter(app, conf):
        return FunctionsWebhookMiddleware(app, conf)
    return webhook_filter
