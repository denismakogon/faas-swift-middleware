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
from swift.proxy.controllers.base import get_container_info

from eventlet import Timeout
import six
if six.PY3:
    from eventlet.green.urllib import request as urllib2
else:
    from eventlet.green import urllib2


class FunctionsWebhookMiddleware(object):

    def __init__(self, app, conf):
        self.app = app
        self.logger = get_logger(conf, log_route='serverless_functions')

    def __call__(self, env, start_response):
        req = Request(env)
        try:
            if "x-function-url" in req.headers:
                version, account, container, obj = split_path(req.path_info, 4, 4, True)
                self.logger.info("Version {}, account {}, container {}, object {}"
                                 .format(version, account, container, obj))

                resp = req.get_response(self.app)
                if obj and is_success(resp.status_int) and req.method == 'PUT':
                    # container_info may have our new sysmeta key
                    # create a POST request with obj name as body
                    webhook = req.headers.get("x-function-url")
                    webhook_req = urllib2.Request(webhook, data=json.dumps({
                        "x-auth-token": req.headers.get("x-auth-token"),
                        "version": version,
                        "account": account,
                        "container": container,
                        "object": obj,
                        "project_id": account[account.index('_') + 1:],
                    }))
                    with Timeout(60):
                        try:
                            result = urllib2.urlopen(webhook_req).read()
                            self.logger.info("Function worked fine. Result {}"
                                             .format(str(result)))
                        except (Exception, Timeout):
                            self.logger.exception(
                                'failed POST to webhook %s' % webhook)
                        else:
                            self.logger.info(
                                'successfully called webhook %s' % webhook)
        except ValueError:
            # not an object request
            pass

        return resp


def filter_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)

    def webhook_filter(app, conf):
        return FunctionsWebhookMiddleware(app, conf)
    return webhook_filter
