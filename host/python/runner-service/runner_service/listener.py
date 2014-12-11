# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import socket
import sys
import os
import json
import uuid

import BaseHTTPServer

from .handlers import runner_handlers

class RequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    REQUESTS = {}

    def log_message(self, format, *args):
        '''
        Override log message to bypass certain behaviors which assume tcp
        sockets
        '''
        pass

    def log_error(self, format, *args):
        '''
        Override log error to bypass certain behaviors which assume tcp
        sockets
        '''
        print(args)

    def send_json(self, status, payload):
        '''
        Respond to incoming http request...

        :param int status:
        :param dict payload: payload to send as json to the socket.
        '''
        payload = json.dumps(payload)
        self.send_response(status)
        self.send_header('Content-Length', len(payload))
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        pass

    def do_POST(self):
        content_length = self.headers.getheader('content-length', 0)
        payload = json.loads(self.rfile.read(int(content_length)))
        handler = self.path[1:]
        method = 'do_' + handler

        # No matter what we send application/json
        if hasattr(self, method):
            try:
                func = getattr(self, method)
                result = func(payload)
            except Exception as e:
                self.send_json(500, { 'message': str(e) })
            else:
                self.send_json(200, result)
        else:
            self.send_json(404, { message: 'Unknown path :' + self.path })


    def do_test_end(self, data):
        print 'TEST-END | %s' % data['test']

    def do_test_start(self, data):
        print 'TEST-START | %s' % data['test']

    def do_test_status(self, data):
        print 'TEST-STATUS | %s | %s' % (data['subtest'], data['status'])

    def do_start_runner(self, payload):
        '''
        Begin a runner

        :param str|None binary: Target binary (usually b2g-bin) for desktop.
        :param dict options: Options specific to the buildapp type.
        '''
        binary = payload.get('binary')
        options = payload.get('options', {})

        handler_args = {
            'symbols_path': options.get('symbols_path')
        }

        if 'b2g_home' in options:
            handler_args['b2g_home'] = options['b2g_home']

        if options['buildapp'] == 'device' and 'serial' in options:
            handler_args['serial'] = options['serial']

        if 'dump_path' in options:
            handler_args['dump_path'] = options['dump_path']

        start_id = str(uuid.uuid4())
        handler = runner_handlers[options['buildapp']](**handler_args)
        handler.start_runner(binary, options)

        self.REQUESTS[start_id] = handler

        return { 'id': start_id }

    def do_stop_runner(self, payload):
        handler = self.REQUESTS.pop(payload['id'])
        handler.stop_runner()
        handler.cleanup()
        return {}