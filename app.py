import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
import hashlib
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # avoid graphical backend issues
import matplotlib.pyplot as plt
import PyPDF2, docx
from collections import defaultdict
from datetime import datetime, timezone
from dateutil import parser
from werkzeug.utils import secure_filename

# Configuration
env_secret = os.environ.get('SECRET_KEY', 'dev_secret')
app = Flask(__name__, instance_relative_config=True)
app.secret_key = env_secret

# Ensure instance folder for SQLite
os.makedirs(app.instance_path, exist_ok=True)

# File upload config
app.config['UPLOAD_FOLDER'] = os.path.join(app.instance_path, 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# SQLite configuration
db_path = os.path.join(app.instance_path, 'database.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# allow multithreaded access
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'connect_args': {'check_same_thread': False}}

db = SQLAlchemy(app)

def default_timestamp():
    return datetime.now(timezone.utc)

# Models
class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Analysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    results_json = db.Column(db.Text, nullable=False)
    mode = db.Column(db.String(20), nullable=False)
    keywords = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=default_timestamp)

with app.app_context():
    db.create_all()

@app.before_request
def make_session_permanent():
    session.permanent = True

# Utility functions
headers = {"User-Agent": os.environ.get('USER_AGENT', "Mozilla/5.0")}

# Routes
@app.route('/', methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            msg = 'Veuillez saisir nom d’utilisateur et mot de passe'
        else:
            hash_password = hashlib.sha1((password + env_secret).encode()).hexdigest()
            try:
                account = Account.query.filter_by(username=username, password=hash_password).first()
            except Exception as e:
                app.logger.error(f"DB error during login: {e}")
                flash('Erreur de connexion à la base de données')
                return render_template('login.html', msg=msg)
            if account:
                session.update({
                    'loggedin': True,
                    'id': account.id,
                    'username': account.username,
                    'email': account.email
                })
                return redirect(url_for('home'))
            msg = 'Nom d’utilisateur ou mot de passe incorrect'
    return render_template('login.html', msg=msg)

@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = ''
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        email = request.form.get('email', '').strip()
        # validation
        if not username or not password or not email:
            msg = 'Veuillez remplir tous les champs'
        elif Account.query.filter_by(username=username).first():
            msg = 'Ce nom d’utilisateur existe déjà'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            msg = 'Adresse email invalide'
        else:
            hash_password = hashlib.sha1((password + env_secret).encode()).hexdigest()
            try:
                new_account = Account(username=username, password=hash_password, email=email)
                db.session.add(new_account)
                db.session.commit()
                msg = 'Enregistrement réussi'
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"DB error during registration: {e}")
                msg = 'Erreur lors de l\'enregistrement'
    return render_template('register.html', msg=msg)

@app.route('/home')
def home():
    if not session.get('loggedin'):
        return redirect(url_for('login'))
    return render_template('accueil.html', username=session.get('username'))

@app.route('/users')
def users():
    if not session.get('loggedin'):
        return redirect(url_for('login'))
    users_list = Account.query.with_entities(Account.username, Account.email, Account.created_at).order_by(Account.created_at.desc()).all()
    return render_template('users.html', users=users_list)

@app.route('/previsions')
def previsions():
    if not session.get('loggedin'):
        return redirect(url_for('login'))
    session_keys = ['resultats_analyse','mode','mots_cles','graph_url','error_message']
    for key in session_keys:
        session.pop(key, None)
    return render_template('previsions.html')

@app.route('/contact', methods=['GET','POST'])
def contact():
    if not session.get('loggedin'):
        return redirect(url_for('login'))
    return render_template('contact.html', username=session.get('username'), email=session.get('email',''))

@app.route('/resultats', methods=['GET','POST'])
def resultats():
    resultats_analyse = session.get('resultats_analyse')
    mode = session.get('mode')
    mots_cles = session.get('mots_cles')
    graph_url = session.get('graph_url')
    error_message = session.get('error_message') or (resultats_analyse is None and "Aucune analyse effectuée.")
    return render_template('resultats.html', resultats_analyse=resultats_analyse, mode=mode, mots_cles=mots_cles, graph_url=graph_url, error_message=error_message)

@app.route('/analyser', methods=["POST"])
def analyser():
    mode = request.form.get('mode')
    mots_cles = request.form.get('keywords','')
    analyse_result = None
    error_message = None
    graph_url = None
    try:
        if mode == 'document':
            document = request.files.get('document')
            if not document:
                raise ValueError("Veuillez télécharger un document.")
            fname = secure_filename(document.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
            document.save(path)
            texte = extraction_du_texte(path)
            if not texte:
                raise ValueError("Impossible de lire le document.")
            sentences = division_en_phrases(texte)
            analyse_result = recherche_mots_cles(sentences, mots_cles)
            phrases = [item['texte'] for lst in analyse_result.values() for item in lst]
            if phrases:
                graph_url = generate_graph(phrases, mots_cles)
        elif mode == 'site':
            site = request.form.get('site_url') or request.form.get('site_select')
            annee = request.form.get('annee')
            annee = int(annee) if annee and annee.isdigit() else None
            if not site:
                raise ValueError("Veuillez saisir une URL.")
            analyse_result = analyse_site(site, mots_cles, annee)
            if not analyse_result:
                error_message = "Aucun contenu trouvé pour les mots-clés spécifiés."
        else:
            raise ValueError("Mode d'analyse inconnu.")
    except Exception as e:
        error_message = str(e)
        app.logger.error(f"Erreur analyse: {e}")
    session.update({
        'resultats_analyse': analyse_result,
        'mode': mode,
        'mots_cles': mots_cles,
        'graph_url': graph_url,
        'error_message': error_message
    })
    return redirect(url_for('resultats'))

# Extraction & analysis functions below (unchanged)...
def extract_paragraphs_from_url(url):
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, 'html.parser')
        date_str=None
        tag = soup.find('meta', {'property':'article:published_time'}) or soup.find('time')
        if tag and tag.has_attr('content'):
            date_str=tag['content']
        elif tag and tag.has_attr('datetime'):
            date_str=tag['datetime']
        date_obj = None
        if date_str:
            try: date_obj = parser.parse(date_str)
            except: pass
        paragraphs=[]
        for p in soup.find_all('p'):
            t=p.get_text(strip=True)
            if t:
                paragraphs.append({'texte':t,'source':url,'date':date_obj or 'Date inconnue'})
        return paragraphs
    except:
        return []

def extract_links_from_url(url):
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text,'html.parser')
        links=set()
        for a in soup.find_all('a',href=True):
            href=a['href'].strip()
            if href and not href.startswith(('javascript:','mailto','#')):
                links.add(urljoin(url,href))
        return list(links)
    except:
        return []

def analyse_site(url, keywords, annee=None):
    result=defaultdict(list)
    kws=[k.strip().lower() for k in keywords.split(',') if k.strip()]
    pages=extract_paragraphs_from_url(url)
    if annee:
        pages=[p for p in pages if isinstance(p['date'], datetime) and p['date'].year==annee]
    for p in pages:
        for kw in kws:
            if kw in p['texte'].lower(): result[kw].append(p)
    for link in extract_links_from_url(url):
        for p in extract_paragraphs_from_url(link):
            if not annee or (isinstance(p['date'], datetime) and p['date'].year==annee):
                for kw in kws:
                    if kw in p['texte'].lower(): result[kw].append(p)
    return dict(result)

def extraction_du_texte(fichier):
    ext=os.path.splitext(fichier)[1].lower()
    txt=""
    try:
        if ext=='.pdf':
            r=PyPDF2.PdfReader(fichier)
            for pg in r.pages: txt+=pg.extract_text() or ''
        elif ext=='.docx':
            d=docx.Document(fichier)
            for p in d.paragraphs: txt+=p.text+"\n"
        elif ext=='.txt':
            with open(fichier,encoding='utf-8') as f: txt=f.read()
        else:
            return None
        return txt
    except:
        return None

def division_en_phrases(text):
    return [s.strip() for s in re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s+', text) if s.strip()]

def recherche_mots_cles(sentences, keywords):
    res={}
    for kw in [k.strip() for k in keywords.split(',') if k.strip()]:
        res[kw]=[{'texte':s} for s in sentences if kw.lower() in s.lower()]
    return res

def generate_graph(phrases, keywords):
    kws=[k.strip() for k in keywords.split(',') if k.strip()]
    counts={k:0 for k in kws}
    for ph in phrases:
        lp=ph.lower()
        for k in kws: counts[k]+=lp.count(k.lower())
    df=pd.DataFrame(list(counts.items()),columns=['Mot clé','Fréquence'])
    if df.empty: return None
    plt.figure(figsize=(8,6))
    plt.bar(df['Mot clé'],df['Fréquence'])
    path=os.path.join(app.static_folder,'images')
    os.makedirs(path,exist_ok=True)
    fp=os.path.join(path,'graph.png')
    plt.savefig(fp); plt.close()
    return url_for('static',filename='images/graph.png')

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5001)))
