from flask import Blueprint, render_template, flash, current_app, request, abort, redirect, url_for
from werkzeug.utils import secure_filename
from io import BytesIO

from insight.common.utils import dispatch, aleph_rpc
from insight.models import Sample

mod = Blueprint('samples', __name__, url_prefix='/samples')

@mod.route('/')
@mod.route('/list')
@mod.route('/list/<int:page>')
def list(page=1):

    all_samples = [Sample(s) for s in current_app.datastore.all()]
    
    return render_template('samples/list.html', samples=all_samples)


@mod.route('/download/<sample_id>')
def download(sample_id):

    result = aleph_rpc('aleph.storages.tasks.retrieve', args=[sample_id], queue='store')

    if not result:
        abort(404)

    data = decode_data(result)

    return send_file(BytesIO(data), as_attachment=True, attachment_filename='%s.sample' % sample_id)

@mod.route('/view/<sample_id>')
def view(sample_id):

    sample = current_app.datastore.get(sample_id)

    if not sample:
        abort(404)

    sample_obj = Sample(sample)

    threat_analysis = []
    suspicious_flags = []

    if 'flags' in sample_obj.metadata.keys():
        for analyzer, flags in sample_obj.metadata['flags'].items():

            a = {
                'analyzer': analyzer,
                'info': 0,
                'uncommon': 0,
                'suspicious': 0,
                'malicious': 0,
                'evil_rating': 0,
            }
            
            for flag in flags:
               a[flag['severity']] += 1
               a['evil_rating'] += flag['evil_rating']
               if flag['severity'] in ['suspicious','malicious']:
                suspicious_flags.append(flag)

            threat_analysis.append(a)

    return render_template('samples/view.html', sample = sample_obj, threat_analysis = threat_analysis, suspicious_flags = suspicious_flags)

@mod.route('/artifacts/<sample_id>')
def artifacts(sample_id):

    sample = current_app.datastore.get(sample_id)

    if not sample:
        abort(404)

    return render_template('samples/artifacts.html', sample = Sample(sample))

@mod.route('/analysis/<sample_id>')
def analysis(sample_id):

    sample = current_app.datastore.get(sample_id)

    if not sample:
        abort(404)

    return render_template('samples/analysis.html', sample = Sample(sample))

@mod.route('/samples/submit', methods=['GET','POST'])
def submit():

    if request.method == 'POST':

        files = request.files

        # if user does not select file, browser also
        # submit an empty part without filename
        for key, file in files.items():
            print(file)
            if file.filename == '':
                flash('No selected file', 'error')
                return redirect(request.url)
            if file:
                filename = secure_filename(file.filename)    
                fdata = file.read()
                metadata = {}
                dispatch(fdata, filename=filename)

    return render_template('samples/submit.html')

@mod.route('/samples/search')
def search():
    
    query = request.args.get('q')

    if not query:
        return redirect(url_for('samples.list'))

    search_result = [Sample(s) for s in current_app.datastore.search(query)]

    return render_template('samples/list.html', samples = search_result, query=query)
