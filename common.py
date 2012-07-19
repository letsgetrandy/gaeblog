from google.appengine.ext.webapp import template
from google.appengine.ext import db
from google.appengine.api import users
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


class Handler(webapp2.RequestHandler):
    ''' Enhanced webapp.Handler class '''

    template_name = ''
    context_vars = {}
    user = None
    require_admin = False

    def __init__(self, request, response):
        self.initialize(request, response)
        user = users.get_current_user()
        if user:
            self.user = user

    def dispatch(self):
        #check for bad user-agents
        try:
            ua = self.request.headers['User-Agent']
            exp = re.compile(r'Ezooms')
            if exp.search(ua):
                self.abort(403)
        except KeyError:
            pass

        #add trailing slashes to urls
        if self.request.path[-1:] != '/':
            return self.redirect(self.request.path + '/')

        #see if admin is required
        if self.require_admin:
            if not self.user:
                self.redirect(users.create_login_url(self.request.uri))
            else:
                if self.user.email() not in settings.BLOG_ADMINS:
                    self.abort(403)

        super(Handler, self).dispatch()

    def render(self, template_name=None, context_vars=None):
        ''' render a template as a response '''
        if template_name is None:
            template_name = self.template_name
        if context_vars is None:
            context_vars = self.context_vars
        context_vars['STATIC_URL'] = settings.BLOG_STATIC_BASE
        context_vars['settings'] = settings
        if self.user:
            context_vars['user'] = self.user
            context_vars['logout_url'] = users.create_logout_url(
                    self.request.uri)
            if self.user.email() in settings.BLOG_ADMINS:
                context_vars['is_admin'] = True

        path = settings.TEMPLATES % template_name
        self.response.out.write(template.render(path, context_vars))

    def error(self, code):
        super(Handler, self).error(code)
        if code == 404:
            # Output 404 page
            #self.error(404)
            self.render(template_name='404.html')


class Handle404(Handler):
    def get(self):
        self.error(404)


class HandleStaticPage(Handler):
    def get(self):
        self.render()


class BaseModel(db.Model):

    @staticmethod
    def getkey(self, name=None):
        classname = self.__class__.__name__
        if name is None:
            name = 'default_%s' % classname.lower()
        return db.Key.from_path(classname, name)
