from flask import Flask, render_template

from datetime import datetime
from slugify import slugify

from insight.config import settings
from insight.datastores.elasticsearch import Elasticsearch
from insight.views import *
from insight.cache import cache

def create_app():

    app = Flask(__name__)


    # Patch config
    app.config['SECRET_KEY'] = settings.get('secret_key')
    app.config['DEBUG'] = settings.get('debug')

    # Add blueprints
    app.register_blueprint(general.mod)
    app.register_blueprint(samples.mod)

    # Register Error handler
    @app.errorhandler(404)
    def page_error_404(e):

        return render_template('errors/404.html'), 404

    # Register extensions
    app.datastore = Elasticsearch()
    cache.init_app(app, config={'CACHE_TYPE': 'simple'})

    # Register Custom Filters
    app.jinja_env.filters['slug'] = jinja_filter_format_slugify
    app.jinja_env.filters['fromkey'] = jinja_filter_format_fromkey
    app.jinja_env.filters['datetime'] = jinja_filter_format_datetime
    app.jinja_env.filters['is_list'] = jinja_filter_is_list

    return app

# Custom filters
def jinja_filter_format_datetime(value, format='medium'):
    if format == 'full':
        format="%Y-%m-%dT%H:%M:%S.%f"
    elif format == 'medium':
        format="%Y-%m-%d %H:%M:%S"

    _date = datetime.fromtimestamp(value)
    return _date.strftime(format)

def jinja_filter_format_slugify(value):

    return slugify(value).lower()

def jinja_filter_format_fromkey(value, sep='_'):

    separated = value.split(sep)
    return ' '.join(separated).title()

def jinja_filter_is_list(value):
    return isinstance(value, list)
