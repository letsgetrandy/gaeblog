from google.appengine.ext.webapp import template
from django import template as django_template


register = template.create_template_register()


@register.tag
def csrf_token(parser, token):
    #token = context.request.cookies.get('csrf_token')
    #return '<input type="hidden" name="csrf_token" value="%s">' % token
    return FormatCsrfToken()


class FormatCsrfToken(django_template.Node):
    def __init__(self):
        pass

    def render(self, context):
        token = context.request.cookies.get('csrf_token')
        return '<input type="hidden" name="csrf_token" value="%s">' % token


@register.tag
def url(parser, token):
    return FormatUrlTag()


class FormatUrlTag(django_template.Node):
    def __init__(self):
        pass

    def render(self, context):
        return 'foo!'


@register.simple_tag
def test_tag():
    return "TEST!"
