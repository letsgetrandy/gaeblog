import os


#basic values
PROJECT_ROOT = os.path.dirname(__file__)

#template path
TEMPLATES = os.path.join(PROJECT_ROOT, 'templates', '%s')

#blog settings
BLOG_NAME = 'My Awesome Blog'
BLOG_DOMAIN_NAME = 'www.myblog.com'
BLOG_BASE_PATH = '/'
BLOG_BASE_URL = 'http://' + BLOG_DOMAIN_NAME

BLOG_STATIC_BASE = '/'  # S3 example: 'http://example_cdn.s3.amazonaws.com/'
BLOG_IMAGE_BASE = BLOG_STATIC_BASE + 'images/'

#DISQUS integration
USE_DISQUS = False
DISQUS_SHORTNAME = 'myblog'
DISQUS_SITE_NAME = 'http://www.myblog.com/'

#admin emails
BLOG_ADMINS = [
        u'test@example.com',
        u'randy@bbqiguana.com',
    ]
