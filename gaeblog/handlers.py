from google.appengine.api import users
import webapp2
import settings
import os
import re
import sys
import template
from uuid import uuid4


APP_ROOT = os.path.dirname(sys.argv[0])
PROJECT_ROOT = os.path.dirname(__file__)


class CsrfException(Exception):
    pass


class Handler(webapp2.RequestHandler):
    ''' Enhanced webapp.Handler class '''

    template_name = ''
    template_path = os.path.join(APP_ROOT, settings.TEMPLATES, '')
    theme_path = os.path.join(PROJECT_ROOT, 'themes', settings.THEME, '')
    context_vars = {}
    user = None
    use_csrf = True

    def __init__(self, request, response):
        self.initialize(request, response)
        self.init_csrf()
        user = users.get_current_user()
        if user:
            self.user = user

    def init_csrf(self):
        """Issue and handle CSRF token as necessary"""

        self.csrf_token = self.request.cookies.get('csrftoken')
        if not self.csrf_token:
            self.csrf_token = str(uuid4())[:8]
            self.response.set_cookie('csrftoken', self.csrf_token)
        if not self.use_csrf:
            return
        if self.request.method == 'POST' \
            and self.csrf_token != self.request.get('_csrf_token'):
            raise CsrfException('Missing or invalid CSRF token.')

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
        if self.request.path[:5] != '/_ah/':
            if self.request.path[-1:] != '/':
                return self.redirect(self.request.path + '/')
            super(Handler, self).dispatch()

    def render(self, template_name=None, context_vars=None):
        ''' render a template as a response '''
        if template_name is None:
            template_name = self.template_name
        if context_vars is None:
            context_vars = self.context_vars
        context_vars['STATIC_URL'] = settings.BLOG_STATIC_BASE
        context_vars['settings'] = settings
        context_vars['csrf_token'] = self.csrf_token
        if self.user:
            context_vars['user'] = self.user
            context_vars['logout_url'] = users.create_logout_url(
                    self.request.uri)
            if self.user.email() in settings.BLOG_ADMINS:
                context_vars['is_admin'] = True

        path = os.path.join(self.theme_path, template_name)
        self.response.out.write(template.render(path, context_vars,
            True, (self.theme_path, self.template_path,)))

    def handle_exception(self, exception, debug):
        if isinstance(exception, webapp2.HTTPException):
            if exception.code == 404:
                #for root, dirs, files in os.walk(self.user_template_path % '.'):

                #self.response.out.write(self.request.route)
                #self.response.set_status(200)
                self.render(template_name="404.html")
            self.response.set_status(exception.code)
        else:
            self.response.out.write(exception)
            super(Handler, self).handle_exception(exception, debug)


class AdminHandler(Handler):
    ''' '''
    theme_path = os.path.join(PROJECT_ROOT, 'admin_templates', '')

    def dispatch(self):
        if not self.user:
            self.redirect(users.create_login_url(self.request.uri))
        else:
            if self.user.email() not in settings.BLOG_ADMINS:
                self.abort(403)

        super(Handler, self).dispatch()


class PageHandler(Handler):
    ''' '''

    def get(self):
        self.render()


class Handle404(Handler):
    def get(self):
        self.abort(404)

    def post(self):
        self.abort(404)
