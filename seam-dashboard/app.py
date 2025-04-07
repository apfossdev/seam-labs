from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
from models import db, User
from kubernetes import client, config
from flask_bcrypt import Bcrypt

app = Flask(__name__)

# Secret key for session management and flashing messages
app.secret_key = os.getenv('SECRET_KEY', 'a-very-secret-key')

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'postgresql://postgres:super_duper_secret_postgres_password@localhost:5432/podtracker'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
bcrypt = Bcrypt(app)

# Below we create tables if they don't exist
with app.app_context():
  db.create_all()

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':

        username = request.form['username'].strip()
        password = request.form['password']
        role = request.form.get('role', 'user')  # default role is 'user'

        if User.query.filter_by(username=username).first():
            flash('Username already taken. Please choose another.', 'error')
            return render_template('register.html')

        pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')

        new_user = User(username=username, password_hash=pw_hash, role=role)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if not user:
            flash('Unknown username.', 'error')
            return render_template('login.html')

        if not bcrypt.check_password_hash(user.password_hash, password):
            flash('Incorrect password.', 'error')
            return render_template('login.html')

        session['user_id']  = user.id
        session['username'] = user.username
        session['role']     = user.role

        if user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('dashboard'))

    return render_template('login.html')

@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()
        v1 = client.CoreV1Api()
        pods = v1.list_namespaced_pod(namespace="new-beginnings")
        pod_names = [pod.metadata.name for pod in pods.items]
    except Exception as e:
        pod_names = []
        flash(f'Error listing pods: {e}', 'error')
    
    try:
        v1_apps = client.AppsV1Api()
        deployments = v1_apps.list_namespaced_deployment(namespace="new-beginnings")
        deployment_names = [
            f"{dep.metadata.name} (Replicas: {dep.spec.replicas})"
            for dep in deployments.items
        ]
    except Exception as e:
        deployment_names = []
        flash(f'Error listing deployments: {e}', 'error')

    # Render the dashboard template
    return render_template('dashboard.html', username=session['username'], pods=pod_names, deployments=deployment_names)

@app.route('/logout')
def logout():
    # Clear the session to log the user out
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/admin-dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    # Ensure admin is logged in
    if session.get('role') != 'admin':
        flash('Admin access required.', 'error')
        return redirect(url_for('login'))

    # Handle pod deletion
    if request.method == 'POST':
        pod_name = request.form.get('pod_name')
        if pod_name:
            try:
                # Load Kubernetes config
                try:
                    config.load_incluster_config()
                except:
                    config.load_kube_config()

                v1 = client.CoreV1Api()
                v1.delete_namespaced_pod(name=pod_name, namespace="new-beginnings")
                flash(f'Pod "{pod_name}" deleted successfully!', 'success')
            except Exception as e:
                flash(f'Error deleting pod: {e}', 'error')

    # Fetch the list of pods
    try:
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()

        v1 = client.CoreV1Api()
        pods = v1.list_namespaced_pod(namespace="new-beginnings")
        # Filter out pods that are in the process of being deleted
        pod_names = [
            pod.metadata.name
            for pod in pods.items
            if pod.metadata.deletion_timestamp is None
        ]
    except Exception as e:
        pod_names = []
        flash(f'Error fetching pods: {e}', 'error')

    # Render the admin dashboard template
    return render_template('admin_dashboard.html', username=session['username'], pods=pod_names)

@app.route('/create-pod', methods=['POST'])
def create_pod():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    pod_name = request.form['pod_name'].strip()
    image = request.form.get('image', 'nginx:latest').strip()

    # Basic validation
    if not pod_name:
        flash('Pod name cannot be empty.', 'error')
        return redirect(url_for('dashboard'))

    try:
        # Load Kubernetes config
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()

        v1 = client.CoreV1Api()
        pod_manifest = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": pod_name},
            "spec": {
                "containers": [
                    {"name": pod_name, "image": image}
                ]
            }
        }
        # Create the pod in your namespace
        v1.create_namespaced_pod(namespace="new-beginnings", body=pod_manifest)
        flash(f'Pod "{pod_name}" created successfully!', 'success')
    except Exception as e:
        flash(f'Error creating pod: {e}', 'error')

    return redirect(url_for('dashboard'))

@app.route('/create-deployment', methods=['POST'])
def create_deployment():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    deployment_name = request.form['deployment_name'].strip()
    image = request.form['image'].strip()
    replicas = int(request.form['replicas'])
    cpu_requests = request.form['cpu_requests'].strip()
    memory_requests = request.form['memory_requests'].strip()
    cpu_limits = request.form['cpu_limits'].strip()
    memory_limits = request.form['memory_limits'].strip()

    # Validate the number of replicas
    if replicas < 1 or replicas > 5:
        flash('Replicas must be between 1 and 5.', 'error')
        return redirect(url_for('dashboard'))

    try:
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()

        v1_apps = client.AppsV1Api()

        # Define the deployment spec
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": deployment_name},
            "spec": {
                "replicas": replicas,
                "selector": {"matchLabels": {"app": deployment_name}},
                "template": {
                    "metadata": {"labels": {"app": deployment_name}},
                    "spec": {
                        "containers": [
                            {
                                "name": deployment_name,
                                "image": image,
                                "resources": {
                                    "requests": {
                                        "cpu": cpu_requests,
                                        "memory": memory_requests,
                                    },
                                    "limits": {
                                        "cpu": cpu_limits,
                                        "memory": memory_limits,
                                    },
                                },
                            }
                        ]
                    },
                },
            },
        }

        # Create the deployment in the "new-beginnings" namespace
        v1_apps.create_namespaced_deployment(namespace="new-beginnings", body=deployment)
        flash(f'Deployment "{deployment_name}" with {replicas} replicas created successfully!', 'success')
    except Exception as e:
        flash(f'Error creating deployment: {e}', 'error')

    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
