from keystone.common import config


#config applicable to all index methods.
PAGE_LIMIT = None


def get_url(req):
    return '%s://%s:%s%s' % (
        req.environ['wsgi.url_scheme'],
        req.environ.get("SERVER_NAME"),
        req.environ.get("SERVER_PORT"),
        req.environ['PATH_INFO'])


def get_marker_limit_and_url(req):
    marker = req.GET["marker"] if "marker" in req.GET else None
    limit = req.GET["limit"] if "limit" in req.GET else PAGE_LIMIT
    url = get_url(req)

    return (marker, limit, url)


def configure_pagination(options):
    """Load pagination configuration specified in the options."""
    global PAGE_LIMIT
    PAGE_LIMIT = config.get_option(
            options, 'page_limit', type='int', default=25)
