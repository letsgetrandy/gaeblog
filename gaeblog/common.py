from google.appengine.ext.webapp import template
from google.appengine.ext import db
import webapp2
import settings
import re


def slugify(s):
    ''' lowercases, converts spaces to dashes, strips non-alphanum chars '''
    s = s.lower()
    s = re.sub('\s+', '-', s)
    s = re.sub('[^\w-]+', '', s)
    return s


def render_to_response(template_name, context_vars, context_instance=None):
    ''' fake some Django syntax '''
    path = settings.TEMPLATES % template_name
    #add some context vars
    context_vars['STATIC_URL'] = settings.BLOG_STATIC_BASE
    context_vars['settings'] = settings
    return webapp2.Response(template.render(path, context_vars))


class RequestContext():
    ''' no-op to fake some Django syntax '''
    def __init__(self, a):
        return None


class BaseModel(db.Model):

    @staticmethod
    def getkey(self, name=None):
        classname = self.__class__.__name__
        if name is None:
            name = 'default_%s' % classname.lower()
        return db.Key.from_path(classname, name)
