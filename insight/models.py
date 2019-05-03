from insight.common.utils import count_dict

class Sample(object):

    id = None
    sample = None
    metadata = {}

    def __init__(self, sample, tracking_data):

        self.id = sample['_id']
        self.sample = sample
        self.metadata = self.sample['_source']
        self.tracking_data = tracking_data['_source']

    def total_flags(self):

        if 'flags' not in self.metadata.keys():
            return 0

        count = 0

        for analyzer, flags in self.metadata['flags'].items():
            count += len(flags)

        return count

    def total_mitre_attack_tactics(self):

        if 'flags' not in self.metadata.keys():
            return 0

        tactics = []

        for analyzer, flags in self.metadata['flags'].items():
            for flag in flags:
                mid = flag['mitre_attack_id']
                if mid and mid not in tactics:
                    tactics.append(mid)

        return len(tactics)

        
    def total_artifacts(self):

        count = 0

        for item in count_dict(self.metadata['artifacts'], skip='strings'):
            count += item

        return count

    def evil_rating(self):

        total_evil = 0

        if 'flags' in self.metadata.keys():
            for analyzer, flags in self.metadata['flags'].items():
                for flag in flags:
                    total_evil += flag['evil_rating']

        return total_evil

    @property
    def filename(self):
        return self.tracking_data['known_filenames'][0]

    @property
    def filetype(self):
        return self.metadata['filetype']

    @property
    def screen_name(self):
        return "%s [%s]" % (self.filename, self.id)


class Datastore(object):

    def __init__(self):
        
        pass

    def all(self, start, size):
        raise NotImplementedError('all function must be implemented on this component')

    def get(self, sample_id):
        raise NotImplementedError('get function must be implemented on this component')

    def search(self, query, start, size):
        raise NotImplementedError('search function must be implemented on this component')

    def count(self, query):
        raise NotImplementedError('count function must be implemented on this component')

    def count_all(self):
        raise NotImplementedError('count_all function must be implemented on this component')

    def count_processing_samples(self):
        raise NotImplementedError('count_processing_samples function must be implemented on this component')

    def count_analyzing_samples(self):
        raise NotImplementedError('count_analyzing_samples function must be implemented on this component')

