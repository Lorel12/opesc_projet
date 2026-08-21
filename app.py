
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

from utils import extraction_du_texte, division_en_phrases, recherche_mots_cles, format_display_date
from scraper import extract_paragraphs_from_url, extract_links_from_url, analyse_site, extract_article_preview
from graph import generate_graph
from database import init_db, get_db_connection


user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
headers = {"User-Agent": user_agent}

app = Flask(__name__)
app.secret_key = 'your secret key'
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="requests")

init_db()

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
                         (username, hash_password, email, datetime.now().isoformat()))
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
    rows = conn.execute('SELECT username, email, created_at FROM accounts ORDER BY created_at DESC').fetchall()
    conn.close()

    users = []
    for row in rows:
        user = dict(row)
        user['created_at'] = format_display_date(user['created_at'])
        users.append(user)

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
    if not session.get('loggedin'):
        return redirect(url_for('login'))

    mode = request.form.get('mode')
    mots_cles = request.form.get('keywords')
    analyse_result = {}
    graph_url = None
    error_message = None
    source_label = ''
    doc = None
    site = None
    try:
        if mode == 'document':
            doc = request.files.get('document')
            if not doc or not doc.filename:
                raise ValueError('Veuillez télécharger un document.')
            source_label = doc.filename
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
            source_label = site or ''
            annee = request.form.get('annee')
            annee = int(annee) if annee and annee.isdigit() else None
            if site:
                paragraphs_data = extract_paragraphs_from_url(site)
                if not paragraphs_data:
                    error_message = "Ce site ne semble pas être scrapable."
                else:
                    analyse_result = analyse_site(site, mots_cles, annee)
                    if isinstance(analyse_result, dict) and 'error' in analyse_result:
                        error_message = analyse_result['error']
                        analyse_result = {}
                    else:
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
                'date': format_display_date(item.get('date')),
                'keyword': keyword
            })

    session['paragraphs'] = paragraphs
    session['keywords'] = mots_cles
    session['source'] = source_label
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

    # Récupération des éléments de session
    paragraphs = session.get('paragraphs', [])
    keywords = session.get('keywords', [])
    source = session.get('source', '')
    date = session.get('date', '')
    type_analyse = session.get('type_analyse', '')
    error_message = session.pop('error_message', None)

    #Pagination
    page = request.args.get('page', 1, type=int) or 1
    per_page = 10
    total = len(paragraphs)

    if total > 0:
        total_pages = (total + per_page - 1) // per_page
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        end = start + per_page
        paginated_paragraphs = paragraphs[start:end]

        pagination = {
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'prev_num': page - 1,
            'next_num': page + 1
        }
    else:
        paginated_paragraphs = []
        pagination = {
            'page': 1,
            'per_page': per_page,
            'total_pages': 1,
            'has_prev': False,
            'has_next': False,
            'prev_num': 1,
            'next_num': 1
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
        pagination=pagination,
        error_message=error_message
    )


@app.route('/actualites')
def actualites():
    if not session.get('loggedin'):
        return redirect(url_for('login'))
    conn = get_db_connection()
    articles = conn.execute('SELECT * FROM articles ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('actualites.html', articles=articles)


@app.route('/actualites/ajouter', methods=['GET', 'POST'])
def ajouter_article():
    if not session.get('loggedin'):
        return redirect(url_for('login'))

    error_message = None
    form = {'url': '', 'titre': '', 'contenu': '', 'image_url': '', 'date_publication': ''}

    if request.method == 'POST':
        action = request.form.get('action', 'enregistrer')
        form['url'] = request.form.get('url', '').strip()
        form['titre'] = request.form.get('titre', '').strip()
        form['contenu'] = request.form.get('contenu', '').strip()
        form['image_url'] = request.form.get('image_url', '').strip()
        form['date_publication'] = request.form.get('date_publication', '').strip()

        if action == 'previsualiser':
            if not form['url']:
                error_message = "Veuillez saisir une URL à pré-remplir."
            else:
                preview = extract_article_preview(form['url'])
                if 'error' in preview:
                    error_message = preview['error']
                else:
                    form['titre'] = preview.get('titre') or form['titre']
                    form['contenu'] = preview.get('contenu') or form['contenu']
                    form['image_url'] = preview.get('image_url') or form['image_url']
                    form['date_publication'] = format_display_date(preview.get('date_publication'))
            return render_template('ajouter_article.html', form=form, error_message=error_message)

        # action == 'enregistrer'
        if not form['titre']:
            error_message = "Le titre est obligatoire."
            return render_template('ajouter_article.html', form=form, error_message=error_message)

        conn = get_db_connection()
        conn.execute(
            'INSERT INTO articles (user_id, titre, contenu, image_url, url, date_publication) VALUES (?, ?, ?, ?, ?, ?)',
            (session['id'], form['titre'], form['contenu'], form['image_url'], form['url'], form['date_publication'])
        )
        conn.commit()
        conn.close()
        return redirect(url_for('actualites'))

    return render_template('ajouter_article.html', form=form, error_message=error_message)


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
