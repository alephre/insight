from collections import OrderedDict
from elasticsearch import Elasticsearch as ES, NotFoundError

from insight.models import Datastore
from insight.config.constants import DEFAULT_PAGE_SIZE

class Elasticsearch(object):

    engine = None
    index = 'aleph'
    doc_type = 'sample'

    def __init__(self):

        self.engine = ES()

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

        return res['hits']['hits']

    def get(self, sample_id):

        result = self.engine.get(index=self.index, doc_type=self.doc_type, id=sample_id, ignore=404)

        if result['found'] == False:
            return None

        return OrderedDict(sorted(result.items()))

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

        return self.engine.count(index=self.index, doc_type=self.doc_type, body=body)['count']

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
