from flask import Flask, render_template

from datetime import datetime
from slugify import slugify

from insight.config import settings
from insight.datastores.elasticsearch import Elasticsearch
from insight.views import *

def create_app():

    app = Flask(__name__)

    # Patch config
    app.config['SECRET_KEY'] = settings.get('secret_key')
    app.config['DEBUG'] = settings.get('debug')

    # Initialize flask extensions
    #cache.init_app(app)
    #mail.init_app(app)

    # Add blueprints
    app.register_blueprint(general.mod)
    app.register_blueprint(samples.mod)

    # Register Error handler
    @app.errorhandler(404)
    def page_error_404(e):

        return render_template('errors/404.html'), 404

    # Register extensions
    app.datastore = Elasticsearch()

    # Register Custom Filters
    app.jinja_env.filters['slug'] = format_slugify
    app.jinja_env.filters['fromkey'] = format_fromkey
    app.jinja_env.filters['datetime'] = format_datetime

    return app

# Custom filters
def format_datetime(value, format='medium'):
    if format == 'full':
        format="%Y-%m-%dT%H:%M:%S.%f"
    elif format == 'medium':
        format="%Y-%m-%d %H:%M:%S"

    _date = datetime.fromtimestamp(value)
    return _date.strftime(format)

def format_slugify(value):

    return slugify(value).lower()

def format_fromkey(value):

    separated = value.split('_')
    return ' '.join(separated).title()
