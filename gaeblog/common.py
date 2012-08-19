from google.appengine.ext.webapp import template
from google.appengine.ext import db
from google.appengine.api.images import Image, JPEG
import webapp2
import settings
import re


def slugify(s):
    ''' lowercases, converts spaces to dashes, strips non-alphanum chars '''
    s = s.lower()
    s = re.sub('\s+', '-', s)
    s = re.sub('[^\w-]+', '', s)
    return s


def get_image_dimensions(data):
    img = Image(data)
    return (img.width, img.height)


def make_image_thumbnail(data):
    img = Image(data)
    if img.width > img.height:
        size = img.height
    else:
        size = img.width
    left = ((img.width - float(size)) / img.width) / 2
    top = ((img.height - float(size)) / img.height) / 2

    #raise Exception('left %f top %f' % (left, top))
    img.crop(left, top, 1.0 - left, 1.0 - top)
    img.resize(settings.THUMBNAIL_SIZE, settings.THUMBNAIL_SIZE)
    return img.execute_transforms(JPEG)


def make_reduced_image(data):
    img = Image(data)
    if not (img.width > settings.FEATURE_MAX_W and img.height > settings.FEATURE_MAX_H):
        return data
    w_pct = settings.FEATURE_MAX_W / float(img.width)
    h_pct = settings.FEATURE_MAX_H / float(img.height)
    if h_pct < w_pct:
        pct = h_pct
    else:
        pct = w_pct
    img.resize(int(pct * img.width), int(pct * img.height))
    return img.execute_transforms(JPEG)


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
