# general config
THEME = 'grayscale'
TEMPLATES = 'templates'

#blog settings
BLOG_NAME = 'My Awesome Blog'
BLOG_DOMAIN_NAME = 'www.myblog.com'
BLOG_BASE_PATH = '/'
BLOG_BASE_URL = 'http://' + BLOG_DOMAIN_NAME

BLOG_STATIC_BASE = '/'  # S3 example: 'http://example_cdn.s3.amazonaws.com/'

#image handling
BLOG_IMAGE_BASE = BLOG_STATIC_BASE + 'images/'
THUMBNAIL_SIZE = 150
FEATURE_MAX_W = 600
FEATURE_MAX_H = 400

#amazon S3 settings
AWS_ACCESS_KEY_ID = ''
AWS_SECRET_ACCESS_KEY = ''
S3_BUCKET_NAME = ''

#DISQUS integration
USE_DISQUS = False
DISQUS_SHORTNAME = 'myblog'
DISQUS_SITE_NAME = 'http://www.myblog.com/'

#admin emails
BLOG_ADMINS = [
        u'test@example.com',
    ]
