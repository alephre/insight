from flask import Blueprint, render_template, flash, current_app, request, abort, redirect, url_for
from werkzeug.utils import secure_filename
from io import BytesIO

from stix2 import TAXIICollectionSource, Filter
from taxii2client import Collection

from insight.common.utils import dispatch, aleph_rpc
from insight.models import Sample
from insight.config.constants import MA_ENTERPRISE_TAXII_URL

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

    ma_phases, ma_entries = ma_get_definitions()

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

    return render_template('samples/view.html', sample = sample_obj, threat_analysis = threat_analysis, suspicious_flags = suspicious_flags, ma_entries=ma_entries)

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

    sample_obj = Sample(sample)

    # Generate MITRE ATT&CK Matrix
    kill_chain_phases = {
        'initial-access': {},
        'execution': {},
        'persistence': {},
        'privilege-escalation': {},
        'defense-evasion': {},
        'credential-access': {},
        'discovery': {},
        'lateral-movement': {},
        'collection': {},
        'exfiltration': {},
        'command-and-control': {},
    }
    kill_chain_headers = [x.replace('-',' ') for x in kill_chain_phases.keys()]
    ma_phases, ma_entries = ma_get_definitions()

    severity_mapping = {'info': 1, 'uncommon': 2, 'suspicious': 3, 'malicious': 4}

    for f_provider, f_flags in sample_obj.metadata['flags'].items():
        for flag in f_flags:
            for ma in flag['mitre_attack_id']:
                for phase, ids in ma_phases.items():
                    kp = kill_chain_phases[phase]
                    if ma in ids:
                        if not ma in kp.keys():
                            kp[ma] = {
                                'highest_severity': 0,
                                'flags': []
                            }
                        severity_rating = severity_mapping[flag['severity']] 
                        kp[ma]['highest_severity'] = severity_rating if severity_rating > kp[ma]['highest_severity'] else kp[ma]['highest_severity']
                        kp[ma]['flags'].append(flag)

    return render_template('samples/analysis.html', sample = sample_obj, ma_phases=ma_phases, ma_entries=ma_entries, kill_chain=kill_chain_phases, kill_chain_headers=kill_chain_headers)

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

# MITRE ATT&CK Functions
def ma_get_definitions():

    # Load MITRE's Att&ck Enterprise definitions
    collection = Collection(MA_ENTERPRISE_TAXII_URL)
    tc_source = TAXIICollectionSource(collection)
    stix_filter = Filter("type", "=", "attack-pattern")
    attack = tc_source.query(stix_filter)

    return ma_parse(attack)

def ma_parse(attack):

    phases = {}
    entries = {}

    for entry in attack:
        name = entry['name']
        description = entry['description']
        phase = entry['kill_chain_phases'][0]['phase_name']

        if phase not in phases.keys():
            phases[phase] = []

        entry_id = entry['external_references'][0]['external_id']
        url = entry['external_references'][0]['url']

        phases[phase].append(entry_id)

        entry_body = {
            'name': name,
            'url': url,
            'description': description,
        }

        entries[entry_id] = entry_body

    return (phases, entries)
