from flask import Blueprint, render_template, flash, current_app, request, abort, redirect, url_for
from werkzeug.utils import secure_filename
from io import BytesIO

from stix2 import TAXIICollectionSource, Filter
from taxii2client import Collection
from math import ceil

from insight.common.utils import dispatch, aleph_rpc
from insight.models import Sample
from insight.cache import cache
from insight.config.constants import MA_ENTERPRISE_TAXII_URL, DEFAULT_PAGE_SIZE, CACHE_DEFAULT_TIMEOUT, CACHE_EXTENDED_TIMEOUT

mod = Blueprint('samples', __name__, url_prefix='/samples')

@mod.route('/')
@mod.route('/list')
@mod.route('/list/<int:page>')
def index(page=1):

    if page < 1:
        abort(404)

    total_samples, all_samples = current_app.datastore.all(page)

    if page > 1 and len(all_samples) <= 0:
        abort(404)

    num_pages = ceil(total_samples/DEFAULT_PAGE_SIZE)
    
    return render_template('samples/list.html', samples=all_samples, num_pages=num_pages,page=page)


@mod.route('/download/<sample_id>')
@cache.cached(timeout=CACHE_DEFAULT_TIMEOUT)
def download(sample_id):

    result = aleph_rpc('aleph.storages.tasks.retrieve', args=[sample_id], queue='store')

    if not result:
        abort(404)

    data = decode_data(result)

    return send_file(BytesIO(data), as_attachment=True, attachment_filename='%s.sample' % sample_id)

def traverse_tree(sample_id, nodes_visited = None):

    if not nodes_visited:
        nodes_visited = set()
        nodes_visited.add(sample_id)

    children = current_app.datastore.get_children(sample_id)
    parents = current_app.datastore.get_parents(sample_id)

    for c in children:
        yield [sample_id, c['_id']]
        if c['_id'] not in nodes_visited:
            nodes_visited.add(c['_id'])
            yield from traverse_tree(c['_id'], nodes_visited)

    for p in parents:
        yield [p, sample_id]
        if p not in nodes_visited:
            nodes_visited.add(p)
            yield from traverse_tree(p, nodes_visited)

@mod.route('/universe/<sample_id>')
@cache.cached(timeout=CACHE_DEFAULT_TIMEOUT)
def universe(sample_id):

    sample = current_app.datastore.get(sample_id)

    if not sample:
        abort(404)

    entities = set()
    connections = []
    entity_info = {}

    parent_table = {}

    for i in traverse_tree(sample_id):

        parent_entity = i[0]
        child_entity = i[1]

        if child_entity in parent_table.keys():
            parent_table[child_entity].append(parent_entity)
            parent_table[child_entity] = [parent_entity,]

        entities.add(parent_entity)
        entities.add(child_entity)

        connections.append(i)

    tree = {
        'entities': list(entities),
        'connections': connections
    }

    ei = current_app.datastore.mget(list(entities))
    locations = set()

    for e in ei:
        entity_info[e.id] = e
        if e.metadata['filetype'] == 'meta/location':
            locations.add(e)

    return render_template('samples/universe.html', sample=sample, tree=tree, entity_info=entity_info, locations=locations)

@mod.route('/view/<sample_id>')
@cache.cached(timeout=CACHE_EXTENDED_TIMEOUT)
def view(sample_id):

    sample = current_app.datastore.get(sample_id)

    if not sample:
        abort(404)

    ma_phases, ma_entries = ma_get_definitions()

    threat_analysis = []
    suspicious_flags = []

    if 'flags' in sample.metadata.keys():
        for analyzer, flags in sample.metadata['flags'].items():

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

    return render_template('samples/view.html', sample = sample, threat_analysis = threat_analysis, suspicious_flags = suspicious_flags, ma_entries=ma_entries)

@mod.route('/iocs/<sample_id>')
@cache.cached(timeout=CACHE_DEFAULT_TIMEOUT)
def iocs(sample_id):

    sample = current_app.datastore.get(sample_id)

    if not sample:
        abort(404)

    ioc_count = 0

    for ioc_type, iocs in sample.metadata['iocs'].items():
        ioc_count += len(iocs)

    return render_template('samples/iocs.html', sample = sample, ioc_count = ioc_count)


@mod.route('/artifacts/<sample_id>')
@cache.cached(timeout=CACHE_DEFAULT_TIMEOUT)
def artifacts(sample_id):

    sample = current_app.datastore.get(sample_id)

    if not sample:
        abort(404)

    return render_template('samples/artifacts.html', sample = sample)

@mod.route('/analysis/<sample_id>')
@cache.cached(timeout=CACHE_DEFAULT_TIMEOUT)
def analysis(sample_id):

    sample = current_app.datastore.get(sample_id)

    if not sample:
        abort(404)

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
        'command-and-control': {},
        'exfiltration': {},
        'impact': {},
    }
    kill_chain_headers = [x.replace('-',' ') for x in kill_chain_phases.keys()]
    ma_phases, ma_entries = ma_get_definitions()

    severity_mapping = {'info': 1, 'uncommon': 2, 'suspicious': 3, 'malicious': 4}

    for f_provider, f_flags in sample.metadata['flags'].items():
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

    return render_template('samples/analysis.html', sample = sample, ma_phases=ma_phases, ma_entries=ma_entries, kill_chain=kill_chain_phases, kill_chain_headers=kill_chain_headers)

@mod.route('/submit', methods=['GET','POST'])
def submit():

    if request.method == 'POST':

        files = request.files

        # if user does not select file, browser also
        # submit an empty part without filename
        for key, file in files.items():
            if file.filename == '':
                flash('No selected file', 'warning')
                return redirect(request.url)
            if file:
                filename = secure_filename(file.filename)    
                fdata = file.read()
                metadata = {}
                dispatch(fdata, filename=filename)

    return render_template('samples/submit.html')

@mod.route('/search')
@mod.route('/search/<int:page>')
def search(page = 1):
    
    query = request.args.get('q')

    if not query:
        return redirect(url_for('samples.list'))

    total_samples, search_result = current_app.datastore.search(query)

    if page > 1 and len(search_result) <= 0:
        abort(404)

    num_pages = ceil(total_samples/DEFAULT_PAGE_SIZE)
    
    return render_template('samples/list.html', samples=search_result, num_pages=num_pages,page=page, search_query=query)

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
