from celery import Celery
from celery.schedules import crontab
from kubernetes import client, config
from datetime import datetime, timedelta

# Initialize Celery
celery = Celery(
    'tasks',
    broker='redis://localhost:6379/0',  # Redis as the message broker
    backend='redis://localhost:6379/0'  # Redis as the result backend
)

@celery.task
def delete_old_pods():
    try:
        # Load Kubernetes config
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()

        v1 = client.CoreV1Api()
        pods = v1.list_namespaced_pod(namespace="new-beginnings")

        for pod in pods.items:
            # Get pod creation timestamp
            creation_time = pod.metadata.creation_timestamp
            current_time = datetime.utcnow()

            # Check if the pod is older than 2 hours
            if creation_time and (current_time - creation_time.replace(tzinfo=None)) > timedelta(hours=2):
                pod_name = pod.metadata.name
                v1.delete_namespaced_pod(name=pod_name, namespace="new-beginnings")
                print(f"Deleted pod: {pod_name} (older than 2 hours)")
    except Exception as e:
        print(f"Error deleting old pods: {e}")

# Schedule the task to run every 10 minutes
celery.conf.beat_schedule = {
    'delete-old-pods-every-10-minutes': {
        'task': 'celery_worker.delete_old_pods',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
    },
}
celery.conf.timezone = 'UTC'