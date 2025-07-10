
from flask import Flask, render_template, request, redirect, url_for, session, flash
import hashlib
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd
import matplotlib
matplotlib.use('Agg')  
import matplotlib.pyplot as plt
import PyPDF2, docx
from collections import defaultdict
import os, json, sqlite3
from werkzeug.utils import secure_filename
from datetime import datetime
from dateutil import parser

from utils import extraction_du_texte, division_en_phrases, recherche_mots_cles
from scraper import extract_paragraphs_from_url, extract_links_from_url, analyse_site
from graph import generate_graph
from database import init_db, get_db_connection


user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
headers = {"User-Agent": user_agent}

app = Flask(__name__)
app.secret_key = 'your secret key'
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

init_db()

def get_robots_parser(base_url):
    parsed_url = urlparse(base_url)
    if not parsed_url.netloc:  # Vérifie qu'on a bien un domaine valide
        print(f"[Erreur] URL malformée ignorée : {base_url}")
        return None
    ...

@app.route('/', methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hash_password = hashlib.sha1((password + app.secret_key).encode()).hexdigest()

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM accounts WHERE username = ? AND password = ?', (username, hash_password)).fetchone()
        conn.close()
        if user:
            session['loggedin'] = True
            session['id'] = user['id']
            session['username'] = user['username']
            session['email'] = user['email']
            return redirect(url_for('home'))
        else:
            msg = 'Mot de passe incorrect !'
    return render_template('login.html', msg=msg)

@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = ''
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM accounts WHERE username = ?', (username,)).fetchone()
        if user:
            msg = 'Ce nom d\'utilisateur existe déjà !'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            msg = 'Adresse email invalide !'
        elif not re.match(r'[A-Za-z0-9]+', username):
            msg = 'Le nom d\'utilisateur doit contenir uniquement des caractères alphanumériques !'
        elif not username or not password or not email:
            msg = 'Veuillez remplir tous les champs du formulaire !'
        else:
            hash_password = hashlib.sha1((password + app.secret_key).encode()).hexdigest()
            conn.execute('INSERT INTO accounts (username, password, email, created_at) VALUES (?, ?, ?, ?)',
                         (username, hash_password, email, datetime.now()))
            conn.commit()
            conn.close()
            msg = 'Enregistrement terminé avec succès !'
            return redirect(url_for('login'))
        conn.close()
    return render_template('register.html', msg=msg)

@app.route('/users')
def users():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    users = conn.execute('SELECT username, email, created_at FROM accounts ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('users.html', users=users)

@app.route('/home')
def home():
    if 'loggedin' in session:
        return render_template('accueil.html', username=session['username'])
    return redirect(url_for('login'))

@app.route('/previsions')
def previsions():
    if 'loggedin' in session:
        return render_template('previsions.html')
    return redirect(url_for('login'))

@app.route('/contact', methods=['GET','POST'])
def contact():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    return render_template('contact.html',
                           username=session['username'], email=session.get('email', ''))
                           #email=session['email'])

@app.route('/analyser', methods=['POST'])
def analyser():
    mode = request.form.get('mode')
    mots_cles = request.form.get('keywords')
    analyse_result = {}
    graph_url = None
    error_message = None
    try:
        if mode == 'document':
            doc = request.files.get('document')
            if not doc:
                raise ValueError('Veuillez télécharger un document.')
            path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(doc.filename))
            doc.save(path)
            
            text = extraction_du_texte(path)
            sentences = division_en_phrases(text)
            analyse_result = recherche_mots_cles(sentences, mots_cles)
           
            phrases = [p['texte'] for lst in analyse_result.values() for p in lst]
            if phrases:
                graph_url = generate_graph(phrases, mots_cles)
        elif mode == 'site':
            site = request.form.get('site_url') or request.form.get('site_select')
            annee = request.form.get('annee')  
            annee = int(annee) if annee and annee.isdigit() else None
            if site:
                paragraphs_data = extract_paragraphs_from_url(site)
                if not paragraphs_data:
                    error_message = "Ce site ne semble pas être scrapable."
                else:
                    analyse_result = analyse_site(site, mots_cles, annee)  
                    phrases = [p['texte'] for lst in analyse_result.values() for p in lst]
                    if phrases:
                        graph_url = generate_graph(phrases, mots_cles)
            else:
                error_message = "Veuillez saisir une URL."        
        else:
            raise ValueError('Mode inconnu.')
    except Exception as e:
        error_message = str(e)

    for kw, items in analyse_result.items():
        for item in items:
            if isinstance(item.get('date'), datetime):
                item['date'] = item['date'].isoformat()

    conn = get_db_connection()
    cur = conn.execute(
            'INSERT INTO analyses (user_id,mots_cles,mode,resultats,graph_url) VALUES (?,?,?,?,?)',
            (
                session['id'],
                mots_cles,
                mode,
                json.dumps(analyse_result, ensure_ascii=False),
                graph_url
            )
        )
    analysis_id = cur.lastrowid
    conn.commit()
    conn.close()

    session['analysis_id'] = analysis_id
    session['error_message'] = error_message
    # Extraire les paragraphes pour affichage paginé
    paragraphs = []
    for keyword, items in analyse_result.items():
        for item in items:
            paragraphs.append({
                'texte': item.get('texte'),
                'source': item.get('source', ''),
                'date': item.get('date'), 
                'keyword': keyword 
            })
    
    session['paragraphs'] = paragraphs
    session['keywords'] = mots_cles
    session['source'] = site if mode == 'site' else doc.filename
    session['date'] = str(datetime.now().date())
    session['type_analyse'] = mode

    return redirect(url_for('resultats'))


@app.route('/resultats', methods=['GET'])
def resultats():
    if not session.get('loggedin'):
        return redirect(url_for('login'))

    aid = session.get('analysis_id')
    if not aid:
        return render_template('resultats.html', error_message="Aucune analyse en session.")

    conn = get_db_connection()
    row = conn.execute('SELECT * FROM analyses WHERE id=?', (aid,)).fetchone()
    conn.close()

    if not row:
        return render_template('resultats.html', error_message="Analyse introuvable.")

    resultats_analyse = json.loads(row['resultats'])

    for kw, items in resultats_analyse.items():
        for item in items:
            d = item.get('date')
            if isinstance(d, str):
                try:
                    item['date'] = datetime.fromisoformat(d)
                except ValueError:
                    item['date'] = None

    # Récupération des éléments de session
    paragraphs = session.get('paragraphs', [])
    keywords = session.get('keywords', [])
    source = session.get('source', '')
    date = session.get('date', '')
    type_analyse = session.get('type_analyse', '')

    #Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 10
    total = len(paragraphs)

    if total > 0:
        total_pages = (total + per_page - 1) // per_page
        start = (page - 1) * per_page
        end = start + per_page
        paginated_paragraphs = paragraphs[start:end]

        pagination = {
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages
        }
    else:
        paginated_paragraphs = []
        pagination = {
            'page': 1,
            'per_page': per_page,
            'total_pages': 1,
            'has_prev': False,
            'has_next': False
        }

    return render_template(
        'resultats.html',
        resultats_analyse=resultats_analyse,
        mode=row['mode'],
        mots_cles=row['mots_cles'],
        graph_url=row['graph_url'],
        paragraphs=paginated_paragraphs,
        keywords=keywords,
        source=source,
        date=date,
        type_analyse=type_analyse,
        pagination=pagination
    )


if __name__ == "__main__":
    app.run(debug=True)
