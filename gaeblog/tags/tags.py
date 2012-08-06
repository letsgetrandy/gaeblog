from google.appengine.ext.webapp import template
from django import template as django_template


register = template.create_template_register()


class CsrfNode(django_template.Node):
    def __init__(self):
        pass

    def render(self, context):
        token = context.get('csrf_token')
        return '<input type="hidden" name="_csrf_token" value="%s">' % token


@register.tag
def csrf_token(parser, token):
    return CsrfNode()


@register.simple_tag
def test_tag():
    return "TEST!"
