import os
import asyncmongo
import tornado.ioloop
import tornado.web

class MainHandler(tornado.web.RequestHandler):
    @property
    def db(self):
        if not hasattr(self, '_db'):
            self._db = asyncmongo.Client(pool_id='mydb', host='localhost', port=27017, dbname='metrics', dbuser='metrics', dbpass='password')
        return self._db

    @tornado.web.asynchronous
    def get(self):
        self.db.events.find({'user_id': 9357}, limit=1, callback=self._on_response)
        # or
        # conn = self.db.connection(collectionname="...", dbname="...")
        # conn.find(..., callback=self._on_response)

    def _on_response(self, response, error):
        if error:
            raise tornado.web.HTTPError(500)
        self.write(response[0]['session_id'])
        self.finish()

application = tornado.web.Application([
    (r"/", MainHandler),
])

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8888))
    application.listen(port)
    tornado.ioloop.IOLoop.instance().start()
