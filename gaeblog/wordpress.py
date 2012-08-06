from google.appengine.api import memcache
from xml.etree import ElementTree
import models
import datetime
import settings
import re


xmlns = {
        'excerpt': "http://wordpress.org/export/1.2/excerpt/",
        'content': "http://purl.org/rss/1.0/modules/content/",
        'wfw': "http://wellformedweb.org/CommentAPI/",
        'dc': "http://purl.org/dc/elements/1.1/",
        'wp': "http://wordpress.org/export/1.2/",
    }
try:
    register_namespace = ElementTree.register_namespace
except AttributeError:
    def register_namespace(prefix, uri):
        ElementTree._namespace_map[uri] = prefix
for prefix, uri in xmlns.items():
    register_namespace(prefix, uri)


class Import():

    datefmt1 = "%Y-%m-%d %H:%M:%S"
    datefmt2 = "%a, %d %b %Y %H:%M:%S"
    imgre = None
    linkre = None

    def __init__(self, job):
        self.origurl = job.orig_url  # kwargs.get('origurl', None)
        self.imgpath = job.img_path  # kwargs.get('imgpath', None)
        self.linkpath = job.link_path  # kwargs.get('linkpath', None)

    def process(self, xml):
        ''' process the import '''

        #if path replacements were specified, build regular expressions
        if self.origurl:
            if self.imgpath:
                self.imgre = re.compile(
                        r'<img([^>]+src=["\']?)%s%s([^\s"\']+)([\s"\'][^>]+)>' %
                        (self.origurl, self.imgpath))
            if self.linkpath:
                self.linkre = re.compile(
                        r'<a([^>]+href=["\']?)%s%s([^\s"\']+)([\s"\'][^>]+)>' %
                        (self.origurl, self.linkpath))

        #load the tag and category dicts
        self.cat_dict = models.Category.get_dict()
        self.tag_dict = models.Tag.get_dict()

        #build the source tree
        tree = ElementTree.fromstring(xml.encode('utf-8'))

        #iterate the source tree
        for item in tree.findall("channel/item"):
            wptype = item.find('{%s}post_type' % xmlns['wp']).text

            if wptype == 'post':
                self.import_post(item)

            #elif wptype == 'attachment':
            #    self.import_attachment(item)

        #update the cached tag and category dicts
        memcache.set('cat_dict', self.cat_dict, 3600)
        memcache.set('tag_dict', self.tag_dict, 3600)

    def get_meta(self, item, find_key):
        ''' helper to find a particular meta tag '''
        post_meta = item.findall('{%s}postmeta' % xmlns['wp'])
        for m in post_meta:
            key = m.find('{%s}meta_key' % xmlns['wp']).text
            val = m.find('{%s}meta_value' % xmlns['wp']).text
            if key == find_key:
                return val
        return None

    def parse_published_date(self, pubDate):
        ''' helper to process rss dates '''
        if pubDate is None:
            return None
        if pubDate.text[-19:] == '0001 00:00:00 +0000':
            return None
        p = pubDate.text
        try:
            offset = int(p[-5:])
        except:
            offset = 0
        delta = datetime.timedelta(hours=offset)
        publish_date = datetime.datetime.strptime(p[:-6], self.datefmt2)
        publish_date -= delta
        return publish_date

    def scrub(self, postbody):
        s = postbody
        if s:
            if self.linkre:
                s = self.linkre.sub(r'<a\1%s\2\3>' % settings.BLOG_BASE_PATH, s)

            if self.imgre:
                s = self.imgre.sub(r'<img\1%s\2\3>' % settings.BLOG_IMAGE_BASE, s)

        return s

    def import_post(self, item):
        ''' process the import of a post '''
        wpid = item.find('{%s}post_id' % xmlns['wp']).text
        wpstat = item.find('{%s}status' % xmlns['wp']).text
        slug = item.find('{%s}post_name' % xmlns['wp']).text

        post = models.Post.get_or_insert(
                key_name=slug or str(wpid),
            )
        post.title = item.find('title').text
        post.body = self.scrub(item.find('{%s}encoded' % xmlns['content']).text)
        post.slug = slug
        post.legacy_permalink = item.find('link').text

        c = item.find('{%s}post_date' % xmlns['wp']).text
        post.created_date = datetime.datetime.strptime(c, self.datefmt1)

        if wpstat == 'publish':
            post.published = True
            pd = item.find('pubDate')
            post.published_date = self.parse_published_date(pd)

        #post.featured_img = self.get_thumbnail(item)

        #wordpress exports tags and categories under the same name
        cats = item.findall('category')
        for ctg in cats:
            cat_type = ctg.attrib['domain']
            cat_slug = ctg.attrib['nicename']
            cat_name = ctg.text
            if cat_type == 'category':
                if not cat_slug in post.categories:
                    post.categories.append(cat_slug)
                self.check_category(cat_slug, cat_name)

            elif cat_type == 'post_tag':
                if not cat_slug in post.tags:
                    post.tags.append(cat_slug)
                self.check_tag(cat_slug, cat_name)

        post.save()
        return

    def check_category(self, slug, name):
        ''' create category only if it doesn't already exist '''
        if not slug in self.cat_dict:
            models.Category(
                    key_name=slug, slug=slug, name=name
                ).put()
            self.cat_dict[slug] = name

    def check_tag(self, slug, name):
        ''' create tag only if it doesn't already exist '''
        if not slug in self.tag_dict:
            models.Tag(
                    key_name=slug, slug=slug, name=name
                ).put()
            self.tag_dict[slug] = name

    def import_attachment(self, item):
        ''' not implemented. '''
        return
