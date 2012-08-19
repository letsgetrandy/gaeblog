from google.appengine.api import memcache
from xml.parsers import expat
import models
import datetime
import gc
import phpserialize as php
import settings
import re


class WPItem():
    ''' helper object representation of an <item> in wordpress export '''

    def __init__(self):
        self.reset()

    def reset(self):
        self.id = ''
        self.parent = ''
        self.parent_key = ''
        self.post_type = ''
        self.status = ''
        self.title = ''
        self.slug = ''
        self.url = ''
        self.body = ''
        self.post_date = ''
        self.pub_date = ''
        self.featured_image = ''
        self.cat_type = ''
        self.cat_name = ''
        self.categories = {}
        self.tags = {}
        self.meta_key = ''
        self.meta_val = ''
        self.postmeta = {}
        gc.collect()

    def save(self):
        if self.post_type == 'post':
            self.save_post()
        elif self.post_type == 'attachment':
            self.save_attachment()

    def save_post(self):
        if not self.slug:
            self.slug = str(self.id)
        post = models.Post().get_or_insert(key_name=self.slug)
        post.title = self.title
        post.legacy_permalink = self.url
        post.body = self.body
        post.created_date = datetime.datetime.strptime(self.post_date, "%Y-%m-%d %H:%M:%S")
        post.featured_img = self.postmeta.get('_thumbnail_id')
        post.categories = self.categories.keys()
        post.tags = self.tags.keys()
        if self.status == 'publish':
            post.published = True
            post.published_date = self.parse_published_date(self.pub_date)
        post.put()

    def save_attachment(self):
        if not self.parent_key:
            return

        parent = models.Post.get_by_key_name(self.parent_key)

        if not parent:
            return
        att = models.Attachment.get_or_insert(
                str(self.id),
                parent=parent,
            )
        att.title = self.title
        att.filename = self.url
        att.put()

        metadata = self.postmeta.get('_wp_attachment_metadata').encode('utf-8')
        data = php.loads(metadata)
        if 'sizes' in data:
            for key, val in data['sizes'].items():
                var = models.ImageVariant.get_or_insert(
                        parent=att, key_name=key)
                var.width = int(val['width'])
                var.height = int(val['height'])
                var.filename = val['file']
                var.save()

    def parse_published_date(self, pubDate):
        ''' helper to process rss dates '''
        if pubDate is None:
            return None
        if pubDate[-19:] == '0001 00:00:00 +0000':
            return None
        p = pubDate
        try:
            offset = int(p[-5:])
        except:
            offset = 0
        delta = datetime.timedelta(hours=offset)
        publish_date = datetime.datetime.strptime(p[:-6], "%a, %d %b %Y %H:%M:%S")
        publish_date -= delta
        return publish_date


class Import():

    imgre = None
    linkre = None
    filere = None

    job = None
    postids = {}

    def __init__(self, job):
        self.origurl = job.orig_url
        self.imgpath = job.img_path
        self.linkpath = job.link_path
        self.job = job

    def process(self, xml):
        ''' process the import '''

        #if path replacements were specified, build regular expressions
        if self.origurl:
            if self.imgpath:
                self.imgre = re.compile(
                        r'<img([^>]+src=["\']?)%s%s([^\s"\']+)([\s"\'][^>]+)>' %
                        (self.origurl, self.imgpath))
                self.filere = re.compile(
                        r'%s%s(.*)' % (self.origurl, self.imgpath))
            if self.linkpath:
                self.linkre = re.compile(
                        r'<a([^>]+href=["\']?)%s%s([^\s"\']+)([\s"\'][^>]+)>' %
                        (self.origurl, self.linkpath))

        #load the tag and category dicts
        self.cat_dict = models.Category.get_dict()
        self.tag_dict = models.Tag.get_dict()

        #re-encode the xml
        xml = xml.encode('utf-8')

        #process posts
        self.import_items(xml)

        #update the cached tag and category dicts
        memcache.set('cat_dict', self.cat_dict, 3600)
        memcache.set('tag_dict', self.tag_dict, 3600)

    def scrub(self, postbody):
        s = postbody
        if s:
            if self.linkre:
                s = self.linkre.sub(r'<a\1%s\2\3>' % settings.BLOG_BASE_PATH, s)

            if self.imgre:
                s = self.imgre.sub(r'<img\1%s\2\3>' % settings.BLOG_IMAGE_BASE, s)

        return s

    def import_items(self, xml):
        parser = None
        stack = []
        item = WPItem()
        post_type = ''
        post_ids = {}

        def start_elem(name, attrs):
            stack.append(name)
            if stack[-2:] == ['item', 'category']:
                #print parser.GetInputContext(), attrs
                item.cat_type = attrs['domain']
                item.cat_name = attrs['nicename']
            #print "Start element: ", name, attrs
            #print "Context: ", parser.GetInputContext()

        def char_data(data):
            if stack[0:3] != ['rss', 'channel', 'item']:
                return

            xpath = '/'.join(stack[3:])

            if xpath == 'wp:post_type':
                item.post_type = data
            elif xpath == 'title':
                item.title = data
            elif xpath == 'wp:status':
                item.status = data
            elif xpath == 'wp:post_name':
                item.slug = data
            elif xpath == 'link':
                item.url = data
            elif xpath == 'wp:post_id':
                item.id = data
            elif xpath == 'wp:post_date':
                item.post_date = data
            elif xpath == 'pubDate':
                item.pub_date = data
            elif xpath == 'content:encoded':
                item.body += self.scrub(data)
            elif xpath == 'category':
                if item.cat_type == 'category':
                    item.categories[item.cat_name] = data
                    self.check_category(item.cat_name, data)
                elif item.cat_type == 'post_tag':
                    item.tags[item.cat_name] = data
                    self.check_tag(item.cat_name, data)
            elif xpath == 'guid':
                if post_type != 'post':
                    if self.filere:
                        data = self.filere.sub(r'\1', data)
                    item.url = data
            elif xpath == 'wp:post_parent':
                item.parent = data
            elif xpath == 'wp:postmeta/wp:meta_key':
                item.meta_key = data
            elif xpath == 'wp:postmeta/wp:meta_value':
                item.meta_val = data

        def end_elem(name):
            stack.pop()
            if name == 'category':
                item.cat_name = ''
                item.cat_type = ''
            elif name == 'wp:postmeta':
                item.postmeta[item.meta_key] = item.meta_val
                item.meta_key = ''
                item.meta_val = ''
            elif name == 'item':
                if post_type == item.post_type:
                    if post_type == 'attachment':
                        item.parent_key = post_ids.get(item.parent)
                    item.save()
                    if post_type == 'post':
                        post_ids[item.id] = item.slug
                item.reset()
                gc.collect()

        post_type = 'post'
        parser = expat.ParserCreate('utf-8')
        parser.StartElementHandler = start_elem
        parser.EndElementHandler = end_elem
        parser.CharacterDataHandler = char_data
        parser.Parse(xml)

        post_type = 'attachment'
        parser = expat.ParserCreate('utf-8')
        parser.StartElementHandler = start_elem
        parser.EndElementHandler = end_elem
        parser.CharacterDataHandler = char_data
        parser.Parse(xml)

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
