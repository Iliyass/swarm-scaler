import json
import docker
import pandas as pd
from dateutil import parser
from apscheduler.schedulers.blocking import BlockingScheduler
import pprint
# - scaler.enabled=true
# - scaler.replica.max=1
# - scaler.replica.step=1
# - scaler.condition.cpu=80
# - scaler.condition.interval=5m
scheduler = BlockingScheduler()
client = docker.DockerClient(base_url='unix://var/run/docker.sock')

# Spin the Scheduler Daemon
# Register Enabled Services in a Set
# Schedule a job to frequently to
    # get service metrics
    # presist service metrics
    # evaluate service condition
        # if the service condition met
            # issue a scale operation to the service

services = {}



def get_cpu_conditions(service):
    lebels = service.attrs['Spec']['Labels']
    cpu_condition = 'scaler.conditions.cpu'
    for k,v in lebels.items():
        if k == cpu_condition:
            return 80

def map_services_labels(slabels):
    labels = {}
    for k,v in slabels.items():
        if 'scaler.condition' in k:
            cpu = slabels.get('scaler.condition.cpu')
            interval = slabels.get('scaler.condition.interval')
            labels['condition'] = {
                'type': 'cpu',
                'value': cpu,
                'interval': interval
            }
        if 'scaler.replica' in k:
            rmax = slabels.get('scaler.replica.max')
            rstep = slabels.get('scaler.replica.step')
            labels['replica'] = {
                'max': rmax,
                'step': rstep
            }
    return labels
index = 0
def stats():
    global index
    global services
    for k,v in services.items():
        for id in v.get('containers', []):
            stats = client.containers.get(id).stats(stream=False)
            series = services[k].get('stats')
            rt = stats.get('read')
            tu = None
            cond = v['labels']['condition']
            if cond.get('type') == 'cpu':
                tu = stats.get('cpu_stats').get('cpu_usage').get('total_usage')
            if cond.get('type') == 'memory':
                tu  = stats.get('memory_stats').get('usage')
            services[k]['stats'] = pd.concat([series,  pd.Series([tu], index=[rt])])
    if index == 10:
        import pdb; pdb.set_trace()
    index +=1

def get_enabled_services():
    es = client.services.list(filters={"label": "scaler.enabled=true"})
    return es

def register_services(services):
    es = get_enabled_services()
    for s in es:
        if s.id not in services:
            services[s.id] = {
                'labels': map_services_labels(s.attrs['Spec']['Labels']),
                'containers': [ ts['Status']['ContainerStatus']['ContainerID'] for ts in s.tasks() ],
                'stats': pd.Series(dtype='int64')
            }
    return services

def check_condition(sid):
    service = services[sid]
    if service['stats'].median() >= service['labels']['condition']['value']:
        client.services.get(sid).scale(service['labels']['replica']['step'])

def register_stats(services):
    for s in services.keys():
        scheduler.add_job(stats, 'interval', args=[s], seconds=5)

# TODO: Implement events func from docker clients
def sync_services():
    global services
    services = register_services(services)

def main():
    global services
    services = register_services(services)
    for sk, sv in services.items():
        interval = int(sv['labels']['condition']['interval'])
        print(f"Schedule check_condition for {sk}")
        scheduler.add_job(check_condition, 'interval', minutes=interval, args=[sk])
    print(f"Running Stats Job")
    scheduler.add_job(stats, 'interval', seconds=5)

main()
print('Started')
scheduler.add_job(sync_services, 'interval', minutes=5)
scheduler.start()