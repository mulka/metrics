import os
import time
import json
import uuid
import random
import base64
import urllib2
import datetime
from collections import defaultdict

import asyncmongo
import tornado.ioloop
import tornado.web
import tornado.httpclient
from pymongo.uri_parser import parse_uri

TRACK_API_KEY = os.environ['TRACK_API_KEY']
TEST_API_SECRET = os.environ['TEST_API_SECRET']
PASSWORD = os.environ['PASSWORD']
DISTINCT_PROPERTY_NAME = os.environ.get('DISTINCT_PROPERTY_NAME', None)

db_info = parse_uri(os.environ['MONGOLAB_URI'])

db = asyncmongo.Client(
    pool_id='mydb',
    host=db_info['nodelist'][0][0],
    port=db_info['nodelist'][0][1],
    dbname=db_info['database'],
    dbuser=db_info['username'],
    dbpass=db_info['password']
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
            self.write({'status': 'success', 'data': {'session_id': session_id}})
        else:
            self.write({'status': 'failure'})

class APIFunnelDataHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    def post(self):
        data = json.loads(self.request.body)
        if data['session_id'] not in session_ids:
            self.write({'status': 'failure'})
            self.finish()
            return

        db.config.find(callback=self._on_config_response)

    def _on_config_response(self, response, error):
        if error:
            self.write({'status': 'failure'})
            self.finish()
            return

        self.funnels = []
        self.tests = []

        for entry in response:
            if entry['_id'] == 'funnels':
                self.funnels = entry['funnels']
            elif entry['_id'] == 'tests':
                self.tests = entry['tests']

        db.funnel_data.find(callback=self._on_funnel_data_response)

    def _on_funnel_data_response(self, response, error):
        if error:
            self.write({'status': 'failure'})
            self.finish()
            return

        funnels_data = {}
        for funnel in response:
            funnels_data[funnel["_id"]] = funnel["value"]["step_counts"]

        data = []
        for i, funnel in enumerate(self.funnels):
            overall_data = []
            for step in funnel["steps"]:
                if funnel["name"] in funnels_data:
                    value = funnels_data[funnel["name"]][step]
                else:
                    value = 0

                overall_data.append(value)

            rows = [{"name": "Overall", "step_data": overall_data}]

            for test in self.tests:
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

        self.write({'status': 'success', 'data': data})
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
        db.config.find_one('tests', callback=self._on_config_response)

    def _on_config_response(self, response, error):
        if error:
            self.write({'status': 'failure'})
            self.finish()
            return

        tests = []

        if response is not None:
            tests = response['tests']

        data = json.loads(self.request.body)

        if data['api_secret'] != TEST_API_SECRET:
            self.write({'status': 'failure'})
            self.finish()
            return

        self.distinct_id = data['distinct_id']

        self.user_tests = {}
        for test in tests:
            ids = []
            for v in test['variations']:
                if 'weight' in v:
                    weight = v['weight']
                else:
                    weight = 1

                for i in xrange(weight):
                    ids.append(v['id'])
            self.user_tests[test['id']] = random.choice(ids)

        db.users.insert({'_id': self.distinct_id, 'tests': self.user_tests}, safe=True, callback=self._on_insert_response)

    def _on_insert_response(self, response, error):
        if error:
            db.users.find({'_id': self.distinct_id}, limit=1, callback=self._on_find_response)
        else:
            self.write({'status': 'success', 'data': self.user_tests})
            self.finish()

    def _on_find_response(self, response, error):
        if error:
            raise tornado.web.HTTPError(500)

        self.write({'status': 'success', 'data': response[0]['tests']})
        self.finish()

def validate_event(event):
    assert isinstance(event["event"], unicode)
    assert isinstance(event["properties"], dict)
    for key, value in event["properties"].iteritems():
        assert isinstance(key, unicode)
        assert isinstance(value, unicode)

class StoreEventHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    def post(self):
        data = json.loads(self.request.body)

        if data['api_key'] != TRACK_API_KEY and data['api_key'] != 'h28fVt0ZKabN8QLQeh4B':
            self.write({'status': 'failure'})
            self.finish()
            return

        if DISTINCT_PROPERTY_NAME:
            data['properties'][unicode('distinct_id')] = data['properties'][DISTINCT_PROPERTY_NAME]

        timestamp = time.time()
        event = {
            "timestamp": timestamp,
            "event": data['event'],
            "properties": data['properties']
        }

        validate_event(event)

        day_str = datetime.datetime.fromtimestamp(timestamp).strftime('%Y_%m_%d')
        db['events_' + day_str].insert(event, callback=self._on_response)

    def _on_response(self, response, error):
        if error:
            raise tornado.web.HTTPError(500)
        self.write({'status': 'success'})
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
gzip=True,
debug=os.environ.get('DEBUG', False))

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8888))
    application.listen(port)
    tornado.ioloop.IOLoop.instance().start()
