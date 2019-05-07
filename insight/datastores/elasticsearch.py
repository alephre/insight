from werkzeug.contrib.cache import SimpleCache
from collections import OrderedDict
from elasticsearch import Elasticsearch as ES, NotFoundError

from insight.models import Datastore, Sample
from insight.config.constants import DEFAULT_PAGE_SIZE

class Elasticsearch(Datastore):

    engine = None
    index = 'aleph-samples'
    tracking_index = 'aleph-tracking'
    doc_type = 'sample'
    cache = None

    def __init__(self):

        self.engine = ES()
        self.cache = SimpleCache()

    def all(self, page=1, size=DEFAULT_PAGE_SIZE):

        body = {
                'query': {
                    'match_all': {},
                },
                "sort": {
                    "timestamp": {
                        'order': 'desc'
                    },
                }
            }

        start = ((page - 1) * size)

        res = self.raw_search(body, start=start, size=size)

        total = res['hits']['total']
        entries = res['hits']['hits']

        return (total, self.entries_to_samples(entries))

    def entries_to_samples(self, entries):

        rv = []
        if not entries:
            return rv

        entry_table = {}

        for entry in entries:
            sample_id = entry['_id']
            entry_table[sample_id] = {'metadata': entry, 'tracking_data': {}}

        # Get tracking data for retrieved ids
        tracking_data = self._mget(list(entry_table.keys()), index=self.tracking_index)

        for td in tracking_data:
            sample_id = td['_id']
            entry_table[sample_id]['tracking_data'] = td

        # Add return values
        for sample_id, sample_data in entry_table.items():
            if '_source' in sample_data['metadata'] and '_source' in sample_data['tracking_data']:
                rv.append(Sample(sample_data['metadata'], sample_data['tracking_data']))

        return rv

    def _mget(self, ids, index=None):

        if not index:
            index = self.index

        if not isinstance(ids, list):
            raise ValueError("ids is not a list")

        body = { 'ids': ids }

        result = self.engine.mget(index=index, doc_type=self.doc_type, body=body, ignore=404)

        if 'docs' not in result:
            return None

        return result['docs']


    def _get(self, sample_id, index=None):

        if not index:
            index = self.index

        result = self.engine.get(index=index, doc_type=self.doc_type, id=sample_id, ignore=404)

        if result['found'] == False:
            return None

        return OrderedDict(sorted(result.items()))

    def mget(self, sample_ids):

        metadata = {s['_id']:s for s in self._mget(sample_ids)}
        tracking_data = {s['_id']:s for s in self._mget(sample_ids, index=self.tracking_index)}

        if not metadata or not tracking_data:
            return None

        entries = []

        for sample_id, v in metadata.items():
            entries.append(Sample(metadata[sample_id], tracking_data[sample_id]))

        return entries

    def get(self, sample_id):

        metadata = self._get(sample_id)
        tracking_data = self._get(sample_id, index=self.tracking_index)

        if not metadata or not tracking_data:
            return None

        return Sample(metadata, tracking_data)

    def get_parents(self, sample_id):

        rv = self.cache.get('get-parents-%s' % sample_id)

        if not rv:
            
            tracking_data = self._get(sample_id, index=self.tracking_index)

            if not tracking_data:
                return []

            rv = tracking_data['_source']['parents']

        return rv

    def get_children(self, sample_id):

        rv = self.cache.get('get-children-%s' % sample_id)

        if not rv:

            search_body = {
                "query": {
                    "bool": {
                        "must": [
                            { "term": { "parents": sample_id } }
                        ]
                    }
                }
            }

            result = self.raw_search(search_body, index=self.tracking_index)

            rv = result['hits']['hits']

        return rv

    def raw_search(self, body, q=None, start=0, size=DEFAULT_PAGE_SIZE, index=None):

        if not index:
            index = self.index

        result = []

        try:
            hits = self.engine.search(index=index, doc_type=self.doc_type, q=q, from_=start, size=size, body=body)
        except NotFoundError:
            pass
        except Exception:
            raise

        return hits
    

    def search(self, query, page=1, size=DEFAULT_PAGE_SIZE):

        start = ((page - 1) * size)

        result = []

        body = {
            "sort": {
                "timestamp": {
                    'order': 'desc'
                },
            }
        }

        hits = self.raw_search(body, start=start, size=size, q=query)

        total = hits['hits']['total']
        entries = hits['hits']['hits']

        return (total, self.entries_to_samples(entries))

    def count(self, body):

        return self.engine.count(index=self.tracking_index, doc_type=self.doc_type, body=body)['count']

    # Aux Methods 

    # Counters
    def count_all(self):

        body = {
            "query": {
                "match_all" : {}
            }
        }
        return self.count(body)

    def count_processing_samples(self):
        body = {
            "query": {
                "bool" : {
                    "filter" : [
                        {"script" : {"script" : {"source": "!doc['processors_completed'].containsAll(doc['processors_dispatched'])", "lang": "painless"}}},
                    ]
                }
            }
        }

        return self.count(body)

    def count_analyzing_samples(self):
        body = {
            "query": {
                "bool" : {
                    "filter" : [
                        {"script" : {"script" : {"source": "!doc['analyzers_completed'].containsAll(doc['analyzers_dispatched'])", "lang": "painless"}}},
                    ]
                }
            }
        }

        return self.count(body)

    # Graph Data
    def sample_histogram(self, size=24, interval="1h"):

        histogram = {}

        hist_body = {
            "aggs" : {
                "samples_over_time" : {
                    "date_histogram" : {
                        "field" : "timestamp",
                        "interval" : interval,
                        "min_doc_count": 0
                    }
                }
            }
        }
        hist_result = self.raw_search(hist_body)['aggregations']

        for h in hist_result['samples_over_time']['buckets']:
            histogram[h['key_as_string']] = h['doc_count']

        return histogram
    
    def sample_diversity(self):

        diversity = {}

        div_body = {
            "aggs" : {
                "genres" : {
                    "terms" : { "field" : "filetype" }
                }
            }
        }
        div_result = self.raw_search(div_body)['aggregations']

        for d in div_result['genres']['buckets']:
            diversity[d['key']] = d['doc_count']

        return diversity
