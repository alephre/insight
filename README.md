# Insight UI
A simple yet complete web interface for Aleph built on Python 3 and Flask

## Requisites
- Backend: The Insight UI needs only read access to the Elasticsearch index. 
- Python 3: Insight UI is tested with python version 3.6.8 and is known to work with 3.5.x. 
  - *Python 2 is untested and not supported.*

*Note: If you want Insight to be able to submit samples into the pipeline, you must configure the RabbitMQ backend with an user with sufficient permissions to reach the 'aleph.task.process' task (usually on the 'manager' queue/exchange).*

## Installation
1. Create the insight-ui folder and `cd` into it
   `mkdir insight-ui`
    `cd insight-ui`
2. Checkout the git repo:
    `git checkout <REPO_URL>`
3. Create a virtualenv for the dependencies
    `virtualenv venv-insight` or `pyenv virtualenv 3.6.8
4. Install dependencies
    `pip3 install -r requirements.txt`

## Running
- `FLASK_APP="main.py" flask run` (Normal)
- `FLASK_APP="main.py" FLASK_DEBUG=1 flask run` (Debug mode)
- `FLASK_APP="main.py" flask run --host 0.0.0.0` (Listening on all interfaces, default=localhost)
