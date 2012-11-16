import os
import time
import json
import base64

import asyncmongo
import tornado.ioloop
import tornado.web

API_SECRET = 'shhh'

db = asyncmongo.Client(
    pool_id='mydb',
    host='localhost',
    port=27017,
    dbname='metrics',
    dbuser='metrics',
    dbpass='password'
)

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
        data = json.loads(base64.b64decode(self.get_argument('data')))
        db.mixpanel.insert(data, callback=self._on_response)
    def _on_response(self, response, error):
        if error:
            raise tornado.web.HTTPError(500)
        self.write(json.dumps({'status': 'success'}))
        self.finish()


application = tornado.web.Application([
    # (r"/", MainHandler),
    (r"/store_event", StoreEventHandler),
    (r"/track/", MixpanelTrackHandler),
])

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8888))
    application.listen(port)
    tornado.ioloop.IOLoop.instance().start()
