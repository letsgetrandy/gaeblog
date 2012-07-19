from google.appengine.ext import webapp2
from common import Handler


class Handle404(Handler):
    def get(self):
        self.error(404)
        self.render(template_name='404.html')


app = webapp2.WSGIApplication([
            ('/.*', Handle404),
        ], debug=True)
