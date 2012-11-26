import os
import time
import json
import uuid
import random
import base64
import urllib2
from collections import defaultdict

import asyncmongo
import tornado.ioloop
import tornado.web
import tornado.httpclient

from config import API_SECRET, PASSWORD, DB, FUNNELS, TESTS

db = asyncmongo.Client(
    pool_id='mydb',
    host=DB["host"],
    port=DB["port"],
    dbname=DB["name"],
    dbuser=DB["username"],
    dbpass=DB["password"]
)

session_ids = set()

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        f = open('index.html')
        self.write(f.read())
        f.close()

class APILoginHandler(tornado.web.RequestHandler):
    def post(self):
        data = json.loads(self.request.body)
        if data['password'] == PASSWORD:
            session_id = str(uuid.uuid4())
            session_ids.add(session_id)
            self.write(json.dumps({'status': 'success', 'data': {'session_id': session_id}}))
        else:
            self.write(json.dumps({'status': 'failure'}))

class APIFunnelDataHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    def post(self):
        data = json.loads(self.request.body)
        if data['session_id'] not in session_ids:
            self.write(json.dumps({'status': 'failure'}))
            self.finish()
            return

        db.funnel_data.find(callback=self._on_response)

    def _on_response(self, response, error):
        if error:
            self.write(json.dumps({'status': 'failure'}))
            self.finish()
            return

        funnels_data = {}
        for funnel in response:
            funnels_data[funnel["_id"]] = funnel["value"]["step_counts"]

        data = []
        for i, funnel in enumerate(FUNNELS):
            overall_data = []
            for step in funnel["steps"]:
                if funnel["name"] in funnels_data:
                    value = funnels_data[funnel["name"]][step]
                else:
                    value = 0

                overall_data.append(value)

            rows = [{"name": "Overall", "step_data": overall_data}]

            for test in TESTS:
                for v in test["variations"]:
                    step_data = []
                    for step in funnel["steps"]:
                        key = funnel["name"] + ':' + test["id"] + ':' + v["id"]
                        if key in funnels_data:
                            value = funnels_data[key][step]
                        else:
                            value = 0

                        step_data.append(value)
                    rows.append({"name": test["id"] + ':' + v["id"], "step_data": step_data})

            data.append({"name": funnel["name"], "step_names": funnel["steps"], "data": rows})

        self.write(json.dumps({'status': 'success', 'data': data}))
        self.finish()

# class MainHandler(tornado.web.RequestHandler):
#     @tornado.web.asynchronous
#     def get(self):
#         db.events.find({'user_id': 9357}, limit=1, callback=self._on_response)
#         # or
#         # conn = db.connection(collectionname="...", dbname="...")
#         # conn.find(..., callback=self._on_response)

#     def _on_response(self, response, error):
#         if error:
#             raise tornado.web.HTTPError(500)
#         self.write(response[0]['session_id'])
#         self.finish()

class GetTestsHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    def post(self):
        data = json.loads(self.request.body)

        if data['api_secret'] != API_SECRET:
            self.write(json.dumps({'status': 'failure'}))
            self.finish()
            return

        self.session_id = data['session_id']

        self.tests = {}
        for test in TESTS:
            ids = []
            if 'variations' not in test:
                test['variations'] = [{"id": True}, {"id": False}]

            for v in test['variations']:
                if 'weight' in v:
                    weight = v['weight']
                else:
                    weight = 1

                for i in xrange(weight):
                    ids.append(v['id'])
            self.tests[test['id']] = random.choice(ids)

        db.sessions.insert({'_id': self.session_id, 'tests': self.tests}, safe=True, callback=self._on_insert_response)

    def _on_insert_response(self, response, error):
        if error:
            db.sessions.find({'_id': self.session_id}, limit=1, callback=self._on_find_response)
        else:
            self.write(json.dumps({'status': 'success', 'data': self.tests}))
            self.finish()

    def _on_find_response(self, response, error):
        if error:
            raise tornado.web.HTTPError(500)

        self.write(json.dumps({'status': 'success', 'data': response[0]['tests']}))
        self.finish()

class StoreEventHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    def post(self):
        data = json.loads(self.request.body)

        if data['api_secret'] != API_SECRET:
            self.write(json.dumps({'status': 'failure'}))
            self.finish()
            return

        event = {
            "timestamp": time.time(),
            "session_id": data['session_id'],
            "url": data['url']
        }
        if 'user_id' in data:
            event["user_id"] = data['user_id']

        db.events.insert(event, callback=self._on_response)

    def _on_response(self, response, error):
        if error:
            raise tornado.web.HTTPError(500)
        self.write(json.dumps({'status': 'success'}))
        self.finish()


class MixpanelTrackHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    def get(self):
        self.data_str = self.get_argument('data')
        data = json.loads(base64.b64decode(self.data_str))
        db.mixpanel.insert(data, callback=self._on_db_response)
    def _on_db_response(self, response, error):
        if error:
            self.write('0')
            self.finish()
            return
        http_client = tornado.httpclient.AsyncHTTPClient()
        http_client.fetch("http://api.mixpanel.com/track/?data=" + self.data_str, self._on_mp_response)
    def _on_mp_response(self, response):
        if response.error:
            self.write('0')
            self.finish()
            return

        self.write('1')
        self.finish()


application = tornado.web.Application([
    (r"/", MainHandler),
    (r"/api/login", APILoginHandler),
    (r"/api/funnel_data", APIFunnelDataHandler),
    (r"/api/tests", GetTestsHandler),
    (r"/api/store_event", StoreEventHandler),
    (r"/track/", MixpanelTrackHandler),
],
static_path='static',
gzip=True)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8888))
    application.listen(port)
    tornado.ioloop.IOLoop.instance().start()
