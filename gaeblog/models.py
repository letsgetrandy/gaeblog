import cgi
import datetime
import difflib
import re
import settings
from google.appengine.ext import db
from google.appengine.api import memcache
from django.utils.html import strip_tags
from django.template.defaultfilters import truncatewords
from common import slugify


class Category(db.Model):
    ''' Represents a blog category '''
    slug = db.StringProperty()
    name = db.StringProperty()

    @property
    def permalink(self):
        return '%stopic/%s/' % (settings.BLOG_BASE_PATH, self.slug)

    def __unicode__(self):
        return self.name

    @staticmethod
    def get_dict():
        ''' return the in-memory category dict. build it if doesn't exist '''
        cat_dict = memcache.get('cat_dict')
        if cat_dict is None:
            cat_dict = {}
            cats = Category.all().fetch(1000)
            for cat in cats:
                cat_dict[cat.slug] = cat.name
            memcache.set('cat_dict', cat_dict, 3600)
        return cat_dict

    @staticmethod
    def add(name, slug=None):
        ''' add a new global category and update the memcache '''
        cats = Category.get_dict()
        if slug is None:
            slug = slugify(name)
        if name not in cats.values():
            cats[slug] = name
            memcache.set('cat_dict', cats, 3600)
        cat = Category(key_name=slug, slug=slug, name=name)
        cat.put()
        return cat


class Tag(db.Model):
    ''' Represents a blog tag '''
    slug = db.StringProperty()
    name = db.StringProperty()

    @property
    def permalink(self):
        return '%stag/%s/' % (settings.BLOG_BASE_PATH, self.slug)

    def __unicode__(self):
        return self.name

    @staticmethod
    def get_dict():
        ''' return the in-memory tag dict. load it if not loaded already '''
        tag_dict = memcache.get('tag_dict')
        if tag_dict is None:
            tag_dict = {}
            tags = Tag.all().fetch(1000)
            for tag in tags:
                tag_dict[tag.slug] = tag.name
            memcache.set('tag_dict', tag_dict, 3600)
        return tag_dict

    @staticmethod
    def add(name, slug=None):
        ''' add a new global tag and update the memcache '''
        tags = Tag.get_dict()
        if slug is None:
            slug = slugify(name)
        if name not in tags.values():
            tags[slug] = name
            memcache.set('tag_dict', tags, 3600)
        tag = Tag(key_name=slug, slug=slug, name=name)
        tag.put()
        return tag


class Attachment(db.Model):
    ''' Represents an attachment on a blog post '''
    title = db.StringProperty()
    filename = db.StringProperty()

    @property
    def filetype(self):
        img = re.compile(r'\.(jpg|jpeg|gif|png)$')
        pdf = re.compile(r'\.pdf$')
        mp3 = re.compile(r'\.mp3$')
        fn = self.filename.lower()

        if img.search(fn):
            return 'image'
        elif pdf.search(fn):
            return 'pdf'
        elif mp3.search(fn):
            return 'mp3'
        else:
            return 'unknown'

    @property
    def permalink(self):
        filetype = self.filetype
        if filetype == 'image':
            filetype = 'images'
        return '%s%s/%s' % (settings.BLOG_STATIC_BASE, filetype, self.filename)


class ImageVariant(db.Model):
    attachment = db.IntegerProperty()
    #name = db.StringProperty()
    width = db.IntegerProperty()
    height = db.IntegerProperty()
    filename = db.StringProperty()

    @property
    def permalink(self):
        return '%simages/%s' % (settings.BLOG_STATIC_BASE, self.filename)


class RelatedPost(db.Model):
    ''' A very minimal model to generate links to related posts '''
    title = db.StringProperty()
    score = db.FloatProperty()

    @property
    def permalink(self):
        ''' returns the fully-qualified URI to this post '''
        return '%s/%s' % (settings.BLOG_BASE_URL, self.slug)


class Post(db.Model):
    ''' Represents a blog post '''
    published = db.BooleanProperty(default=False)
    created_date = db.DateTimeProperty(auto_now_add=True)
    modified_date = db.DateTimeProperty(auto_now=True)
    published_date = db.DateTimeProperty()
    slug = db.StringProperty()
    author = db.IntegerProperty()
    title = db.StringProperty()
    body = db.TextProperty()
    excerpt = db.StringProperty(default=None)
    categories = db.StringListProperty()
    tags = db.StringListProperty()
    featured_img = db.StringProperty()
    legacy_permalink = db.StringProperty()

    @property
    def attachment_set(self):
        return Attachment().all().ancestor(self).fetch(50)
        #img = Attachment().get_by_key_name(self.featured_img, parent=self)

    def categories_set(self):
        ''' returns a set of categories associated with this post '''
        cats_dict = Category.get_dict()
        cats = []
        for c in self.categories:
            try:
                cats.append(Category(slug=c, name=cats_dict[c]))
            except KeyError:
                pass
        return cats

    def tags_set(self):
        ''' returns the set of tags associated with this post '''
        tags_dict = Tag.get_dict()
        tags = []
        for t in self.tags:
            try:
                tags.append(Tag(slug=t, name=tags_dict[t]))
            except KeyError:
                pass
        return tags

    def get_excerpt(self):
        ''' return an excerpt for this post '''
        if self.excerpt:
            return self.excerpt
        s = strip_tags(self.body)
        return truncatewords(s, 55)

    @property
    def permalink(self):
        ''' returns the fully-qualified URI to this post '''
        if self.slug:
            return '%s/%s' % (settings.BLOG_BASE_URL, self.slug)
        else:
            return '%s/%s' % (settings.BLOG_BASE_URL, self.id)

    def get_slug(self):
        ''' slugify the title '''
        if self.slug:
            return self.slug
        else:
            return Post.slugify(self.title)

    #def status(self):
    #    ''' returns a text representation of the post's status '''
    #    if self.published_date is not None:
    #        if self.published_date < datetime.datetime.now:
    #            return 'Published'
    #        else:
    #            return 'Scheduled'
    #    else:
    #        return 'Draft'

    def get_image(self, variant_name):
        ''' get an image variant by name '''
        if not self.featured_img:
            return None
        img = Attachment().get_by_key_name(self.featured_img, parent=self)
        if not img:
            return None
        variant = ImageVariant().get_by_key_name(variant_name, parent=img)
        return variant

    @property
    def get_feature_image(self):
        return self.get_image('medium')

    @property
    def get_thumbnail(self):
        return self.get_image('thumbnail')

    @property
    def get_fullsize_image(self):
        if not self.featured_img:
            return None
        return Attachment().get_by_key_name(self.featured_img, parent=self)

    def related_posts(self):
        ''' returns a list containing related posts '''

        posts = RelatedPost().all().ancestor(self).order('-score').fetch(5)
        if len(posts) < 5:
            posts = self.update_related_posts()
        return posts[:5]

    def update_related_posts(self):
        ''' calculated the related posts '''

        a = self.title.lower()
        cat_set = set(self.categories)
        tag_set = set(self.tags)

        posts = []
        related_posts = []

        posts.extend(Post.all().filter('cats IN ', self.categories))
        posts.extend(Post.all().filter('tags IN ', self.tags))

        posts = list(set(posts))
        if self in posts:
            posts.remove(self)

        for p in posts:
            seq = difflib.SequenceMatcher(a=a, b=p.title.lower())
            score = seq.ratio()
            score += 2 * len(set(p.categories).intersection(cat_set))
            score += 3 * len(set(p.tags).intersection(tag_set))

            if p.key().name() != self.key().name():
                rel = RelatedPost(parent=self, key_name=p.slug)
                rel.title = p.title
                rel.score = score
                rel.put()
                related_posts.append(rel)

                rel = RelatedPost(parent=p, key_name=self.slug)
                rel.title = self.title
                rel.score = score
                rel.put()

        related_posts.sort(key=lambda x: x.score, reverse=True)
        return related_posts

    def find_links(self):
        ''' returns a list of links in the post body '''
        exp = re.compile('<a[^>]+href="[^">]+"[^>]*>[^<]+</a>')
        found_links = exp.findall(self.body)
        links = []
        exp1 = re.compile('<a[^>]+title="([^"]+)"[^>]*>[^<]+</a>')
        exp2 = re.compile('<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>')
        for l in found_links:
            m1 = exp1.match(l)
            m2 = exp2.match(l)
            if m2:
                if m1:
                    label = m1.group(1)
                else:
                    label = m2.group(2)
                href = m2.group(1)
                links.append('<a href="%s">%s</a>' % (href, label))
        return links

    def formatted(self):
        ''' format the post for HTML '''
        s = 0
        t = []
        while s > -1:
            m = self.body.find('<pre', s)
            t.append(self.body[s:m].replace('\n', '<br>\n'))
            s = m
            if s > -1:
                m = self.body.find('>', s)
                t.append(self.body[s:m + 1])  # append the pre tag
                s = m + 1
                m = self.body.find('</pre>', s)
                if m > -1:
                    t.append(cgi.escape(self.body[s:m]) + '</pre')
                    #t.append(self.body[s:m] + '</pre')
                    s = m + 5
        t.append(self.body[-1:])
        return ''.join(t)

    @staticmethod
    def slugify(title):
        ''' slugify the title '''
        s = slugify(title)
        i = 1
        k = Post.get_by_key_name(s)
        while k is not None:
            i += 1
            k = Post.get_by_key_name(s + '-' + str(i))
        if i > 1:
            s += '-' + str(i)
        return s

    @staticmethod
    def recent_posts():
        ''' get recent posts '''
        posts = memcache.get('recent_posts')
        if posts is None:
            posts = Post.all().filter('published = ', True
                    ).filter('published_date < ', datetime.datetime.now()
                    ).order('-published_date').fetch(10)
            memcache.set('recent_posts', posts, 7200)
        return posts

    def __unicode__(self):
        return self.title


class Comment(db.Model):
    ''' represents a comment on a blog post '''
    id = db.IntegerProperty()
    author = db.StringProperty()
    email = db.StringProperty()
    url = db.StringProperty()
    text = db.TextProperty()
