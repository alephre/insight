from flask import Blueprint, render_template, flash, current_app

from insight.models import Sample
from insight.common.utils import check_celery_status

mod = Blueprint('general', __name__) 

# WebApp Funcs
@mod.route('/')
def index():

    # Check celery status
    stack_status = check_celery_status()

    # Counters
    counters = {
        'processing': current_app.datastore.count_processing_samples(),
        'analyzing': current_app.datastore.count_analyzing_samples(),
        'all': current_app.datastore.count_all(),
    }

    # Latest samples
    latest_samples = current_app.datastore.all()

    # Graphs
    div = current_app.datastore.sample_diversity()
    diversity = {
        'data': div.values(),
        'labels': list(div.keys()),
    }

    # Pipeline Histogram
    hist = current_app.datastore.sample_histogram()
    histogram = {
        'data': hist.values(),
        'labels': list(hist.keys()),
    }

    return render_template('general/dashboard.html', samples=latest_samples, counters=counters, diversity=diversity, histogram=histogram, stack_status=stack_status)
