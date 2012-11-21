import os
import time
import json
import uuid
import base64
import urllib2
from collections import defaultdict

import asyncmongo
import tornado.ioloop
import tornado.web
import tornado.httpclient

from config import API_SECRET, PASSWORD, DB, FUNNELS

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
            funnels_data[funnel["_id"]] = funnel["value"]

        data = []
        for i, funnel in enumerate(FUNNELS):
            funnel_data = []
            for step in funnel["steps"]:
                if funnel["name"] in funnels_data:
                    value = funnels_data[funnel["name"]][step]
                else:
                    value = 0

                funnel_data.append({"name": step, "value": value})
            data.append({"name": funnel["name"], "steps": funnel_data})

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

        db.events.insert(event, limit=1, callback=self._on_response)

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
    (r"/store_event", StoreEventHandler),
    (r"/track/", MixpanelTrackHandler),
],
static_path='static',
gzip=True)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8888))
    application.listen(port)
    tornado.ioloop.IOLoop.instance().start()
