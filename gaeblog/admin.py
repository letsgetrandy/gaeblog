#!/usr/bin/env python

from google.appengine.ext import db
from google.appengine.api import taskqueue, memcache
from google.appengine.ext.webapp.util import run_wsgi_app
from operator import itemgetter
from handlers import AdminHandler, Handler, Handle404
from pagedquery import PagedQuery
from common import make_image_thumbnail, make_reduced_image, get_image_dimensions
import webapp2
import models
import datetime
import os
import settings
import S3


class Import(db.Model):
    ''' Represents a single import job '''
    source = db.StringProperty()  # eg, "wordpress"
    created = db.DateTimeProperty(auto_now_add=True)
    link_path = db.StringProperty()
    img_path = db.StringProperty()
    orig_url = db.StringProperty()


class Image:
    ''' Class for persisting Image data when creating a post '''
    def __init__(self, *args, **kwargs):
        if len(args) == 1:
            arr = args[0].split(',')
            self.name = arr[0]
            self.variants = [ImageVariant(s) for s in arr[1:]]
        else:
            self.name = kwargs.get('name')
            self.variants = kwargs.get('variants', [])

    def __str__(self):
        return '%s,%s' % (self.name, ','.join([str(v) for v in self.variants]))

    def __repr__(self):
        return '<Image: %s>' % self.name


class ImageVariant:
    ''' Class for persisting Image variations '''
    def __init__(self, *args, **kwargs):
        if len(args) == 1:
            p, n, w, h = args[0].split('#')
            self.path = p
            self.name = n
            self.width = w
            self.height = h
        else:
            self.path = kwargs.get('path')
            self.name = kwargs.get('name')
            self.width = kwargs.get('width')
            self.height = kwargs.get('height')

    def __str__(self):
        return "%s#%s#%s#%s" % (self.path, self.name,
                self.width or '', self.height or '')

    def __repr__(self):
        return "ImageVariant(path='%s', name='%s', width=%s, height=%s)" % (
                self.path, self.name, self.width, self.height)


class IndexHandler(AdminHandler):
    ''' for the admin home page '''

    def get(self):
        ''' display the admin main page '''
        self.render('admin_index.html')


class UpdSlugs(AdminHandler):
    ''' '''

    def get(self):
        p = models.Post.all().filter('slug = ', None).fetch(1000)
        self.context_vars = {
                'posts': p,
            }
        return self.render('update_slugs.html')

    def post(self):
        data = self.request.POST
        postids = data.getall('postid')
        for p in postids:
            slug = data.get('slug%s' % p)
            post = models.Post.get_by_key_name(p)
            post.slug = slug
            post.put()

        self.response.out.write('done')
        return


class PostsHandler(AdminHandler):
    ''' display all posts '''

    def get(self, page=1):
        query = models.Post.all().order('-published_date')
        pager = PagedQuery(query, 30)
        posts = pager.fetch_page(int(page))

        self.context_vars = {
                'posts': posts,
            }
        return self.render('admin_posts.html')


class DraftsHandler(AdminHandler):
    ''' display drafts '''

    def get(self, page=1):
        query = models.Post.all().filter('published = ', False).order('-created_date')
        pager = PagedQuery(query, 30)
        posts = pager.fetch_page(int(page))

        self.context_vars = {
                'posts': posts,
                'title': 'Drafts',
            }
        return self.render('admin_posts.html')


class PostHandler(AdminHandler):
    ''' handles adding/editing a blog post '''

    def get(self, keyname=None):
        ''' show the blog post edit form '''
        tags = models.Tag.get_dict()
        cats = models.Category.get_dict()
        self.context_vars = {
                'now': datetime.datetime.now(),
                'tags': sorted(tags.items(), key=itemgetter(1)),
                'categories': sorted(cats.items(), key=itemgetter(1)),
            }

        if keyname:
            post = models.Post.get_by_key_name(keyname)
            self.context_vars['post'] = post
        else:
            self.context_vars['title'] = 'New Post'

        self.render('admin_post_form.html')

    def post(self, key=None):
        ''' accept posted data and saves a blog post '''

        data = self.request.POST
        tags = data.getall('tag')
        cats = data.getall('category')

        published_date = data.get('published_date')
        published = data.get('published')

        slug = data.get('slug')
        title = data.get('title')
        if key:
            post = models.Post.get_by_key_name(key)

            #convert non-slugified keynames
            if post.key().name() != slug:
                slug = models.Post.slugify(title)
                p = post
                post = models.Post(key_name=slug)
                post.created_date = p.created_date
        else:
            if not slug:
                slug = models.Post.slugify(title)
            post = models.Post(key_name=slug)

        post.slug = slug
        post.title = title
        post.body = data.get('body')
        post.excerpt = data.get('excerpt')
        post.featured_img = data.get('featured_img')

        formatstr = '%Y-%m-%d %H:%M:%S'

        if published and published != 'false':
            post.published = True
            post.published_date = datetime.datetime.strptime(published_date, formatstr)
            #clear the cached "recent_posts" query
            memcache.delete('recent_posts')
        else:
            post.published = False

        posttags = []
        for t in tags:
            newtag = models.Tag.add(t)
            posttags.append(newtag.slug)
        post.tags = posttags

        postcats = []
        for c in cats:
            newcat = models.Category.add(c)
            postcats.append(newcat.slug)
        post.categories = postcats

        post.save()
        post.update_related_posts()

        images = data.getall('image')
        if images:
            for im in images:
                image = Image(im)
                att = models.Attachment(parent=post, key_name=image.name)
                att.filename = image.name
                att.put()
                for var in image.variants:
                    v = models.ImageVariant(parent=att, key_name=var.name)
                    v.filename = var.path
                    if var.width:
                        v.width = int(var.width)
                    if var.height:
                        v.height = int(var.height)
                    v.put()
            pass

        return self.redirect('/admin/posts/edit/%s/?updated=true' %
                post.key().name())


class PreviewHandler(AdminHandler):

    def post(self):
        ''' creates a preview of a blog post '''
        data = self.request.POST
        key = data.get('key')
        if key:
            post = models.Post.get_by_key_name(key)
        else:
            post = models.Post()
            post.key = {'name': 'preview'}  # dirty hack for template errors
            post.legacy_permalink = None
            post.slug = '/'

        post.title = data.get('title')
        post.body = data.get('body')
        post.tags = data.getall('tag')
        post.categories = data.getall('categories')

        formatstr = '%Y-%m-%d %H:%M:%S'
        pub_date = data.get('published_date')
        post.published_date = datetime.datetime.strptime(pub_date, formatstr)

        post.body = post.body.replace('\n', '<br>')

        links = post.find_links()
        #related_posts = post.related_posts()

        self.context_vars = {
                'post': post,
                'links': links,
                'recent_posts': models.Post.recent_posts()[:5],
                #'related_posts': related_posts,
            }

        self.render('blog_post.html')


class DeleteHandler(AdminHandler):
    ''' handles deleting a post '''

    def post(self, key=None):
        ''' handle deleting a post '''
        if self.request.POST.get('confirmed') != 'true':
            return self.abort(403)

        post = models.Post.get_by_key_name(key)
        if post is None:
            return self.abort(404)

        post.delete()
        memcache.delete('recent_posts')
        return self.redirect('/admin/posts/')


class TagsHandler(AdminHandler):
    ''' display all tags for selection when editing '''

    def get(self, page=1):
        ''' show the admin page for tags '''
        tags = models.Tag.get_dict()

        self.context_vars = {
                'tags': sorted(tags.items(), key=itemgetter(1)),
            }

        return self.render('admin_tags.html')


class TagHandler(AdminHandler):
    ''' add new or edit existing tag '''

    def get(self, keyname=None):
        ''' show the edit page for a tag '''
        self.context_vars = {
            }
        if keyname:
            tag = models.get_by_key_name(keyname)
            self.context_vars['tag'] = tag

        return self.render('admin_tag_form.html')


class CategoriesHandler(AdminHandler):
    ''' display all categories, for selection when editing '''

    def get(self, page=1):
        ''' show the admin page for categories '''
        cats = models.Category.get_dict()
        self.context_vars = {
                'categories': sorted(cats.items(), key=itemgetter(1)),
            }
        return self.render('admin_categories.html')


class CategoryHandler(AdminHandler):
    ''' add new, or edit existing category '''

    def get(self, keyname=None):
        ''' show the edit page for a category '''
        self.context_vars = {
            }
        if keyname:
            category = models.get_by_key_name(keyname)
            self.context_vars['category'] = category

        return self.render('admin_category_form.html')


class ImageLoader(AdminHandler):
    '''  '''

    def get(self):
        key = self.request.GET.get('key')
        if key:
            post = models.Post().get_by_key_name(key)
            atts = models.Attachment().all().ancestor(post).fetch(100)
            attach = []
            for att in atts:
                i = Image(name=att.filename)
                vrnts = models.ImageVariant().all().ancestor(att).fetch(10)
                for vrnt in vrnts:
                    v = ImageVariant(name=vrnt.key().name(), path=vrnt.filename,
                            width=vrnt.width, height=vrnt.height)
                    i.variants.append(v)
                attach.append(i)
        else:
            attach = []
        return self.render('admin_image_upload.html', {'images': attach})

    def post(self):
        ff = self.request.get('img')
        if not ff:
            return
        f = self.request.POST.get('img')
        basename, extension = os.path.splitext(f.filename)
        files = self.request.POST.getall('files')
        files.append(f.filename)

        images = self.request.POST.getall('image')

        conn = S3.Connection(
                settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)
        #generator = S3.QueryStringAuthGenerator(
        #        settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)

        if conn.check_bucket_exists(settings.S3_BUCKET_NAME).status_code != 200:
            self.response.out.write('bucket not found')
            return

        append = 0
        filename = basename + extension
        medium = basename + '-medium' + extension
        thumbnail = basename + '-thumb' + extension
        code = conn.get(settings.S3_BUCKET_NAME, 'images/%s' % filename).http_response.status_code
        while code != 404:
            append -= 1
            filename = basename + str(append) + extension
            thumbnail = basename + str(append) + '-thumb' + extension
            code = conn.get(settings.S3_BUCKET_NAME, 'images/%s' % filename).http_response.status_code

        i = Image(name=f.filename)
        conn.put(settings.S3_BUCKET_NAME, 'images/' + filename,
                S3.S3Object(ff),
                {'x-amz-acl': 'public-read', 'Content-Type': 'image/jpeg'})
        f_medium = make_reduced_image(ff)
        size = get_image_dimensions(f_medium)
        conn.put(settings.S3_BUCKET_NAME, 'images/' + medium,
                S3.S3Object(f_medium),
                {'x-amz-acl': 'public-read', 'Content-Type': 'image/jpeg'})
        i.variants.append(ImageVariant(name="medium", path=medium,
                width=size[0], height=size[1]))
        f_thumb = make_image_thumbnail(ff)
        conn.put(settings.S3_BUCKET_NAME, 'images/' + thumbnail,
                S3.S3Object(f_thumb),
                {'x-amz-acl': 'public-read', 'Content-Type': 'image/jpeg'})
        i.variants.append(ImageVariant(name="thumbnail", path=thumbnail,
            width=settings.THUMBNAIL_SIZE, height=settings.THUMBNAIL_SIZE))
        images.append(i)

        return self.render('admin_image_upload.html', {'files': files, 'images': images})


class FileChunk(db.Model):
    order = db.IntegerProperty()
    data = db.TextProperty()


class ImportHandler(AdminHandler):
    ''' client-facing form for uploading import files '''

    def get(self):
        ''' show the upload form '''
        self.render('admin_import_form.html')

    def post(self):
        ''' store the xml in the database and queue the task to process '''
        importfile = self.request.get('wpfile')

        import_job = Import(source="wordpress")
        import_job.link_path = self.request.get('linkpath')
        import_job.img_path = self.request.get('imgpath')
        import_job.orig_url = self.request.get('origurl')
        import_job.put()

        s = importfile.decode('utf-8')

        #split the string for storing in 1MB GAE limit
        size = 1000000
        chunks = [s[start:start + size] for start in range(0, len(s), size)]

        #save the chunked data
        order = 0
        for c in chunks:
            order += 1
            f = FileChunk(parent=import_job)
            f.order = order
            f.data = c
            f.put()

        #queue backend task to process the import
        taskqueue.add(
                url='/admin/process_import/',
                queue_name='import',
                params={
                        'job': import_job.key().id(),
                    },
                target='importworker',
            )

        #let the user know something happened
        self.response.out.write('created import job #' + str(import_job.key().id()))


class ProcessImport(Handler):
    ''' Handler for queued tasks to process uploaded import files '''

    use_csrf = False

    def post(self):
        ''' worker for the queued task '''

        #load the chunked data
        xml = ''
        jobid = self.request.get('job')

        job = Import().get_by_id(int(jobid))
        chunks = FileChunk().all().ancestor(job).order('order').fetch(100)
        for chunk in chunks:
            xml += chunk.data

        #pick the right importer class
        if job.source == 'wordpress':
            from wordpress import Import
            importer = Import(job)
        else:
            self.abort(401)
            return

        #import the data
        importer.process(xml)
        for chunk in chunks:
            chunk.delete()
        job.delete()
        return


app = webapp2.WSGIApplication([

        (r'/admin/', IndexHandler),

        (r'/admin/image/upload/', ImageLoader),

        (r'/admin/posts/', PostsHandler),
        (r'/admin/posts/page/(\d+)/', PostsHandler),
        (r'/admin/posts/new/', PostHandler),
        (r'/admin/posts/edit/', PostHandler),
        (r'/admin/posts/edit/([\w-]+)/', PostHandler),
        (r'/admin/posts/preview/', PreviewHandler),
        (r'/admin/posts/drafts/', DraftsHandler),
        (r'/admin/posts/delete/([\w-]+)/', DeleteHandler),

        (r'/admin/tags/', TagsHandler),
        (r'/admin/tags/page/(\d+)/', TagsHandler),
        (r'/admin/tags/new/', TagHandler),
        (r'/admin/tags/edit/', TagHandler),
        (r'/admin/tags/edit/([\w-]+)/', TagHandler),

        (r'/admin/categories/', CategoriesHandler),
        (r'/admin/categories/page/(\d+)/', CategoriesHandler),
        (r'/admin/categories/new/([\w-]+)/', CategoryHandler),
        (r'/admin/categories/edit/', CategoryHandler),
        (r'/admin/categories/edit/([\w-]+)/', CategoryHandler),

        (r'/admin/import/', ImportHandler),
        (r'/admin/process_import/', ProcessImport),
        (r'/admin/update_slugs/', UpdSlugs),

        #catch-all
        (r'/.*', Handle404),
    ], debug=True)


def main():
    run_wsgi_app(app)

if __name__ == "__main__":
    main()
