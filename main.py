#!/usr/bin/env python

from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from common import Handler, HandleStaticPage, Handle404
from pagedquery import PagedQuery
from webapp2 import Route, WSGIApplication
import datetime
import models


#load template tags
template.register_template_library('tags.tags')


class IndexHandler(Handler):
    ''' handler for the index page '''

    def get(self):
        ''' view the blog index page '''
        posts_set = models.Post.recent_posts()
        if len(posts_set) < 1:
            return self.render('blog_no_posts.html')

        feature = posts_set[0]

        if len(posts_set) > 1:
            posts = posts_set[1:5]
        else:
            posts = []
        has_next = (len(posts_set) > 5)

        feature.body = feature.body.replace('\n', '<br>')

        self.context_vars = {
                'has_next': has_next,
                'feature': feature,
                'posts': posts,
            }
        self.render('blog_index.html')


class PostHandler(Handler):
    ''' handler for viewing posts '''

    def get(self, slug=None, year=None, month=None):
        ''' view a blog post '''

        post = models.Post.get_by_key_name(slug)
        if post is None:
            return self.error(404)

        #convert non-slugified keynames
        if post.key().name() != post.slug:
            p = models.Post(key_name=post.get_slug())
            p.published = post.published
            p.created_date = post.created_date
            p.modified_date = post.modified_date
            p.published_date = post.published_date
            p.slug = post.slug
            p.author = post.author
            p.title = post.title
            p.body = post.body
            p.excerpt = post.excerpt
            p.tags = post.tags
            p.categories = post.categories
            p.featured_img = post.featured_img
            p.put()
            post.delete()
            post = p

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


class ArchiveHandler(Handler):
    ''' handler for archive pagees '''

    def get(self, year=None, month=None, page=1):
        ''' display one page of archived posts '''
        page = int(page)
        post_query = models.Post.all().filter('published = ', True).filter(
                    'published_date < ', datetime.datetime.now()
                ).order('-published_date')
        q = PagedQuery(post_query, 10)
        posts = q.fetch_page(page)

        self.context_vars = {
                'page_title': 'Blog archive',
                'page': page,
                'posts': posts,
                'path': '/',
                'has_prev': q.has_page(page - 1),
                'has_next': q.has_page(page + 1),
            }

        self.render('blog_archive.html')


class MainArchiveHandler(ArchiveHandler):
    ''' hack for viewing archive pages without year/month '''
    def get(self, page=1):
        super(MainArchiveHandler, self).get(page=int(page))


class CategoryHandler(Handler):
    ''' handler for viewing archived posts by category '''

    def get(self, slug, page=1):
        ''' view one page of archved posts in a category '''
        page = int(page)
        cats = models.Category.get_dict()
        post_query = models.Post.all().filter('published = ', True).filter(
                    'categories = ', slug).filter(
                    'published_date < ', datetime.datetime.now()
                ).order('-published_date')
        q = PagedQuery(post_query, 10)
        posts = q.fetch_page(page)

        self.context_vars = {
                'page_title': cats[slug],
                'page': page,
                'posts': posts,
                'path': '/topic/%s/' % slug,
                'has_prev': q.has_page(page - 1),
                'has_next': q.has_page(page + 1),
            }

        self.render('blog_archive.html')


class TagHandler(Handler):
    ''' handler for viewing archived posts by tag '''

    def get(self, slug, page=1):
        ''' view one page of archived posts with a specified tag '''
        page = int(page)
        tags = models.Tag.get_dict()
        post_query = models.Post.all().filter(
                    'published = ', True
                ).filter(
                    'tags = ', slug
                ).filter(
                    'published_date < ', datetime.datetime.now()
                ).order('-published_date')
        q = PagedQuery(post_query, 10)
        posts = q.fetch_page(page)

        self.context_vars = {
                'page_title': 'Posts about: <em>%s</em>' % tags[slug],
                'page': page,
                'posts': posts,
                'path': '/tag/%s/' % slug,
                'has_prev': q.has_page(page - 1),
                'has_next': q.has_page(page + 1),
            }

        self.render('blog_archive.html')


class RssFeed(Handler):
    ''' handler for generating the rss feed '''

    def get(self):
        ''' Compile the RSS Feed '''
        posts_set = models.Post.all().filter(
                        'published = ', True
                    ).filter(
                        'published_date < ', datetime.datetime.now()
                    ).order('-published_date').fetch(10)
        vars = {
                'posts': posts_set,
            }
        self.response.headers['Content-Type'] = 'application/xml'
        self.render('feed.xml', vars)


#static pages
class AboutPage(HandleStaticPage):
    template_name = 'about.html'


class ContactPage(HandleStaticPage):
    template_name = 'contact.html'


class FaqPage(HandleStaticPage):
    template_name = 'faq.html'

app = WSGIApplication([

        #routes for pages
        Route(r'/about/', AboutPage, name="about"),
        Route(r'/contact/', ContactPage, name="contact"),
	Route(r'/faq/', FaqPage, name="faqs"),

        #routes for tags
        Route(r'/tag/<slug:[\w-]+>/page/<page:\d+>/', TagHandler),
        Route(r'/tag/<slug:[\w-]+>/', TagHandler, name="view_tag"),

        #routes for categories
        Route(r'/topic/<slug:[\w-]+>/page/<page:\d+>/', CategoryHandler),
        Route(r'/topic/<slug:[\w-]+>/', CategoryHandler, name="view_category"),

        #routes for archives
        Route(r'/<year:\d+>/<month:\d+>/page/<page:\d+>/', ArchiveHandler),
        Route(r'/<year:\d+>/<month:\d+>/', ArchiveHandler),
        Route(r'/<year:\d+>/page/<page:\d+>/', ArchiveHandler),
        Route(r'/<year:\d+>/', ArchiveHandler),
        Route(r'/page/<page:\d+>/', ArchiveHandler),

        #routes for posts
        Route(r'/<year:\d+>/<month:\d+>/<slug:[\w-]+>/', PostHandler),
        Route(r'/<year:\d+>/<slug:[\w-]+>/', PostHandler),
        Route(r'/<slug:[\w-]+>/', PostHandler, name="view_post"),

        Route(r'/', IndexHandler, name="index"),

        (r'/feed.*', RssFeed),

        #stop a few hack attempts
        (r'/wp-content.*', Handle404),
        (r'/index.php.*', Handle404),
        (r'/js/.*', Handle404),
        (r'/css/.*', Handle404),
    ], debug=True)


def main():
    run_wsgi_app(app)

if __name__ == "__main__":
    main()
