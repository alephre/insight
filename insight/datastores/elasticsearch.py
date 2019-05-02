from collections import OrderedDict
from elasticsearch import Elasticsearch as ES, NotFoundError

from insight.models import Datastore, Sample
from insight.config.constants import DEFAULT_PAGE_SIZE

class Elasticsearch(Datastore):

    engine = None
    index = 'aleph-samples'
    tracking_index = 'aleph-tracking'
    doc_type = 'sample'

    def __init__(self):

        self.engine = ES()

    def all(self, page=1, size=DEFAULT_PAGE_SIZE):

        entry_table = {}

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

        entries = res['hits']['hits']

        for entry in entries:
            sample_id = entry['_id']
            entry_table[sample_id] = {'metadata': entry, 'tracking_data': {}}

        # Get tracking data for retrieved ids
        tracking_data = self._mget(list(entry_table.keys()), index=self.tracking_index)

        for td in tracking_data:
            sample_id = td['_id']
            entry_table[sample_id]['tracking_data'] = td

        rv = []

        for sample_id, sample_data in entry_table.items():
            rv.append(Sample(sample_data['metadata'], sample_data['tracking_data']))

        return rv

    def _mget(self, ids, index=None):

        if not index:
            index = self.index

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

    def get(self, sample_id):

        metadata = self._get(sample_id)
        tracking_data = self._get(sample_id, index=self.tracking_index)

        if not metadata or not tracking_data:
            return None

        return Sample(metadata, tracking_data)

    def raw_search(self, body, q=None, start=0, size=DEFAULT_PAGE_SIZE):

        result = []

        try:
            hits = self.engine.search(index=self.index, doc_type=self.doc_type, q=q, from_=start, size=size, body=body)
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

        hits = self.raw_search(body, from_=start, size=size, q=query)
        return hits['hits']['hits']

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
                    "terms" : { "field" : "mimetype" }
                }
            }
        }
        div_result = self.raw_search(div_body)['aggregations']

        for d in div_result['genres']['buckets']:
            diversity[d['key']] = d['doc_count']

        return diversity
