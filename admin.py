#!/usr/bin/env python

from google.appengine.ext import db
from google.appengine.api import taskqueue, memcache
from google.appengine.ext.webapp.util import run_wsgi_app
from operator import itemgetter
from common import Handler, Handle404
from pagedquery import PagedQuery
import webapp2
import models
import datetime
import wordpress


class IndexHandler(Handler):
    ''' for the admin home page '''

    require_admin = True

    def get(self):
        ''' display the admin main page '''
        self.render('admin_index.html')


class UpdSlugs(Handler):
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

        self.response.write('done')
        return


class PostsHandler(Handler):
    ''' display all posts '''

    require_admin = True

    def get(self, page=1):
        query = models.Post.all().order('-published_date')
        pager = PagedQuery(query, 30)
        posts = pager.fetch_page(int(page))

        self.context_vars = {
                'posts': posts,
            }
        return self.render('admin_posts.html')


class DraftsHandler(Handler):
    ''' display drafts '''

    require_admin = True

    def get(self, page=1):
        query = models.Post.all().filter('published = ', False).order('-created_date')
        pager = PagedQuery(query, 30)
        posts = pager.fetch_page(int(page))

        self.context_vars = {
                'posts': posts,
                'title': 'Drafts',
            }
        return self.render('admin_posts.html')


class PostHandler(Handler):
    ''' handles adding/editing a blog post '''

    require_admin = True

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
        #if excerpt:
        #    post.excerpt = excerpt

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

        return self.redirect('/admin/posts/edit/%s/?updated=true' %
                post.key().name())


class PreviewHandler(Handler):
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


class DeleteHandler(Handler):
    ''' handles deleting a post '''

    require_admin = True

    def post(self, key=None):
        ''' handle deleting a post '''
        if self.request.POST.get('confirmed') != 'true':
            return self.abort(403)

        post = models.Post.get_by_key_name(key)
        if post is None:
            return self.error(404)

        post.delete()
        memcache.delete('recent_posts')
        return self.redirect('/admin/posts/')


class TagsHandler(Handler):
    ''' display all tags for selection when editing '''

    require_admin = True

    def get(self, page=1):
        ''' show the admin page for tags '''
        tags = models.Tag.get_dict()

        self.context_vars = {
                'tags': sorted(tags.items(), key=itemgetter(1)),
            }

        return self.render('admin_tags.html')


class TagHandler(Handler):
    ''' add new or edit existing tag '''

    require_admin = True

    def get(self, keyname=None):
        ''' show the edit page for a tag '''
        self.context_vars = {
            }
        if keyname:
            tag = models.get_by_key_name(keyname)
            self.context_vars['tag'] = tag

        return self.render('admin_tag_form.html')


class CategoriesHandler(Handler):
    ''' display all categories, for selection when editing '''

    require_admin = True

    def get(self, page=1):
        ''' show the admin page for categories '''
        cats = models.Category.get_dict()
        self.context_vars = {
                'categories': sorted(cats.items(), key=itemgetter(1)),
            }
        return self.render('admin_categories.html')


class CategoryHandler(Handler):
    ''' add new, or edit existing category '''

    require_admin = True

    def get(self, keyname=None):
        ''' show the edit page for a category '''
        self.context_vars = {
            }
        if keyname:
            category = models.get_by_key_name(keyname)
            self.context_vars['category'] = category

        return self.render('admin_category_form.html')


class ImportFile(db.Model):
    source = db.StringProperty()
    order = db.IntegerProperty()
    data = db.TextProperty()


class ImportHandler(Handler):
    ''' client-facing form for uploading import files '''

    require_admin = True

    def get(self):
        ''' show the upload form '''
        self.render('admin_import_form.html')

    def post(self):
        ''' store the xml in the database and queue the task to process '''
        importfile = self.request.get('wpfile')
        linkpath = self.request.get('linkpath')
        imgpath = self.request.get('imgpath')
        origurl = self.request.get('origurl')

        s = importfile.decode('utf-8')

        #split the string for storing in 1MB GAE limit
        size = 1000000
        chunks = [s[start:start + size] for start in range(0, len(s), size)]

        #save the chunked data
        keys = []
        order = 0
        for c in chunks:
            order += 1
            f = ImportFile()
            f.source = "wordpress"
            f.order = order
            f.data = c
            f.put()
            keys.append(f.key().id())

        #queue backend task to process the import
        k = ','.join([str(key) for key in keys])
        taskqueue.add(
                url='/admin/process_import/',
                queue_name='import',
                params={
                        'keys': k,
                        'origurl': origurl,
                        'imgpath': imgpath,
                        'linkpath': linkpath,
                        'source': 'wordpress',
                    },
                target='importworker',
            )

        #let the user know something happened
        self.response.out.write('done.<br>' + k)


class ProcessImport(Handler):
    ''' Handler for queued tasks to process uploaded import files '''

    def post(self):
        ''' worker for the queued task '''

        #load the chunked data
        xml = ''
        keys = self.request.get('keys')
        #raise Exception('keys: ' + keys)

        for key in keys.split(','):
            f = ImportFile.get_by_id(int(key))
            if f is None:
                return
            xml += f.data
            f.delete()

        #raise Exception('success')

        #get passed params
        source = self.request.get('source')
        origurl = self.request.get('origurl')
        imgpath = self.request.get('imgpath')
        linkpath = self.request.get('linkpath')

        #pick the right importer class
        if source == 'wordpress':
            importer = wordpress.Import(origurl=origurl, imgpath=imgpath, linkpath=linkpath)
        else:
            return

        #import the data
        importer.process(xml)
        return


app = webapp2.WSGIApplication([

        (r'/admin/', IndexHandler),

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
