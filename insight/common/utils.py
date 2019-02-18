from datetime import datetime
from base64 import b64encode, b64decode
from celery import Celery

from insight.config.constants import ALEPH_TASK_PROCESS
from insight.config import settings

celery = Celery(__name__,
        broker=settings.get('broker_url'),
        backend=settings.get('result_backend'))

def encode_data(data):
    return b64encode(data).decode('utf-8') 

def decode_data(data):
    return b64decode(data.encode('utf-8')) 

def to_es_date(d): 
    s = d.strftime('%Y-%m-%dT%H:%M:%S.') 
    s += '%03d' % int(round(d.microsecond / 1000.0))
    s += d.strftime('%z') 
    return s

def aleph_rpc(task_name, args, queue=None):

    promise = celery.send_task(task_name, args=args, queue=queue)
    result = promise.wait(timeout=None, propagate=True, interval=1)

def dispatch(data, metadata={}, filename=None):

    metadata['timestamp'] = to_es_date(datetime.utcnow())
    metadata['known_filenames'] = [filename]

    safe_data = encode_data(data)

    if check_celery_status():
        celery.send_task(ALEPH_TASK_PROCESS, queue='manager', args=[safe_data, metadata])
        return True

    return False

def check_celery_status():

    MAX_RUNS = 5
    count = 0

    while count < MAX_RUNS:
        try:
            if celery.control.inspect().active():
                return True
        except Exception as e:
            pass
        count += 1

    return False

def count_dict(d, skip=None):
    for k,v in d.items():
        if skip and k == skip:
            continue        
        if isinstance(v, dict):
            yield from count_dict(v)
        elif isinstance(v, list):
            yield len(v)
        else:            
            yield 1
            
