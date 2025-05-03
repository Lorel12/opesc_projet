from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_pymongo import PyMongo
import hashlib
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd
import matplotlib
matplotlib.use('Agg')  #Ajout obligatoire pour éviter les problèmes de backend graphique
import matplotlib.pyplot as plt
import PyPDF2, docx
from collections import defaultdict
import os, json
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
from dateutil import parser

user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
headers = {"User-Agent": user_agent}

app = Flask(__name__)
app.secret_key = 'your secret key'
app.config['MONGO_URI'] = 'mongodb://localhost:27017/pythonlogin'
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
mongo = PyMongo(app)

@app.route('/', methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form['username']
        password = request.form['password']
        hash_password = hashlib.sha1((password + app.secret_key).encode()).hexdigest()
        account = mongo.db.accounts.find_one({'username': username, 'password': hash_password})
        print(account)

        if account:
            session['loggedin'] = True
            session['id'] = str(account['_id'])
            session['username'] = account['username']
            session['email'] = account.get('email', '')
            return redirect(url_for('home'))
        else:
            msg = 'Mot de passe incorrect!'
    return render_template('login.html', msg=msg)

@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = ''
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form and 'email' in request.form:
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        account = mongo.db.accounts.find_one({'username': username})
        if account:
            msg = 'Ce nom d\'utilisateur existe déjà!'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            msg = 'Adresse email invalide!'
        elif not re.match(r'[A-Za-z0-9]+', username):
            msg = 'Le nom d\'utilisateur doit contenir uniquement des caractères alphanumériques!'
        elif not username or not password or not email:
            msg = 'Veuillez remplir tous les champs du formulaire!'
        else:
            hash_password = hashlib.sha1((password + app.secret_key).encode()).hexdigest()
            mongo.db.accounts.insert_one({'username': username, 'password': hash_password, 'email': email, 'created_at': datetime.now(timezone.utc)
})
            msg = 'Enregistrement terminé avec succès!'
    elif request.method == 'POST':
        msg = 'Veuillez remplir tous les champs du formulaire!'
    return render_template('register.html', msg=msg)

@app.route('/users')
def users():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    
    users_cursor = mongo.db.accounts.find(
        {},
        {'password': 0}
    ).sort('created_at', -1)

    # Convertir en liste pour le template
    users_list = []
    for u in users_cursor:
        
        users_list.append({
            'username': u['username'],
            'email': u['email'],
            'created_at': u.get('created_at')
        })

    return render_template('users.html', users=users_list)

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

    # Récupérer l'email depuis la base
    """ 
    user = mongo.db.accounts.find_one(
       {'username': session['username']},
       {'email': 1, '_id': 0}
    ) 
    #user_email = user.get('email','')
    """
    return render_template('contact.html',
                           username=session['username'], email=session.get('email', ''))
                           #email=session['email'])

@app.route('/resultats', methods=['GET', 'POST'])
def resultats():
    if request.method == 'POST':
        mots_cles = request.form.get('mots_cles')  
        mode = request.form.get('mode')
        
        resultats_analyse = {
            "mot1": [{"texte": "Texte du résultat pour mot1", "source": "source1.com", "date": "2025-04-12"}],
            "mot2": [{"texte": "Texte du résultat pour mot2", "source": "source2.com", "date": "2025-04-11"}]
        }
        
        session['resultats_analyse'] = resultats_analyse
        session['mode'] = mode
        session['mots_cles'] = mots_cles
        
        return render_template('resultats.html', resultats_analyse=resultats_analyse, mode=mode, mots_cles=mots_cles)

    if request.method == 'GET':

        resultats_analyse = session.get('resultats_analyse')
        mode = session.get('mode')
        mots_cles = session.get('mots_cles')
        graph_url = session.get('graph_url')
        error_message = session.get('error_message')
        
        if resultats_analyse is None:
            error_message = "Aucune analyse effectuée."
        
        return render_template('resultats.html', 
                               resultats_analyse=resultats_analyse, 
                               mode=mode, 
                               mots_cles=mots_cles, 
                               graph_url=graph_url, 
                               error_message=error_message)
    else:
        pass

    resultats_analyse = session.get('resultats_analyse')
    mode = session.get('mode')
    mots_cles = session.get('mots_cles')

    if resultats_analyse is None:
        return render_template('resultats.html', error_message="Aucune analyse effectuée.")
    
    return render_template('resultats.html', resultats_analyse=resultats_analyse, mode=mode, mots_cles=mots_cles)

@app.route('/analyser', methods=["POST"])
def analyser():
    mode = request.form.get('mode')
    mots_cles = request.form.get('keywords')
    analyse_result = None
    error_message = None
    graph_url = None

    try:
        if mode == 'document':
            document = request.files.get('document')
            if document:
                filename = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(document.filename))
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                document.save(filename)
                texte = extraction_du_texte(filename)
                if texte:
                    sentences = division_en_phrases(texte)
                    analyse_result = recherche_mots_cles(sentences, mots_cles)
                    # Extraction pour le graphique (on récupère les phrases trouvées)
                    all_found_phrases = []
                    for phrases_list in analyse_result.values():
                        all_found_phrases.extend([item['texte'] for item in phrases_list])
                    if all_found_phrases:
                        graph_url = generate_graph(all_found_phrases, mots_cles)
                else:
                    error_message = "Erreur lors de la lecture du fichier."
            else:
                error_message = "Veuillez télécharger un document."
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
            else:
                error_message = "Veuillez saisir une URL."
        else:
            error_message = "Mode d'analyse inconnu."
    except Exception as e:
        error_message = f"Une erreur inattendue s'est produite : {e}"
        print(f"Erreur lors de l'analyse : {e}")

    session['resultats_analyse'] = analyse_result
    session['mode'] = mode
    session['mots_cles'] = mots_cles
    session['graph_url'] = graph_url
    session['error_message'] = error_message

    return render_template("resultats.html", mode=mode, mots_cles=mots_cles, resultats_analyse=analyse_result, graph_url=graph_url, error_message=error_message)  

def extract_paragraphs_from_url(url):
    try:
        response = requests.get(url)#, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        paragraphs_data = []
       
        date_str = None
        date_tag = soup.find('meta', {'property': 'article:published_time'})
        if date_tag and 'content' in date_tag.attrs:
            date_str = date_tag['content']
        else:
            time_tag = soup.find('time')
            if time_tag and time_tag.has_attr('datetime'):
                date_str = time_tag['datetime']
        
        try:
            if date_str:
                date_str = date_str.replace('CEST', '').replace('CET', '').strip()
                
                # Ajoute un 'T' entre la date et l'heure 
                if re.match(r'^\d{4}-\d{2}-\d{2}\d{2}:\d{2}:\d{2}', date_str):
                    date_str = date_str[:10] + 'T' + date_str[10:]
                
                date_obj = parser.parse(date_str)
            else:
                date_obj = None
        except Exception as ex:
            print(f"Erreur de conversion de la date '{date_str}': {ex}")
            date_obj = None

        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            if text:
                paragraphs_data.append({
                    'texte': text,
                    'source': url,
                    'date': date_obj if date_obj else "Date inconnue"
                })
        return paragraphs_data
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la récupération des paragraphes depuis {url}: {e}")
        return []
        
def extract_links_from_url(url):
    try:
        response = requests.get(url, headers=headers)#, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        links = set()
        for link in soup.find_all('a', href=True):
            href = link['href'].strip()
            # on ignore les liens non pertinents
            if href.startswith("javascript:") or href.startswith("mailto:") or href in ['#', '']:
                continue
            # URL absolue
            full_url = urljoin(url, href)
            links.add(full_url)
        return list(links)
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la récupération des liens depuis {url}: {e}")
        return []

def analyse_site(url, keywords, annee=None):
    resultat = defaultdict(list)
    keywords_list = [kw.strip().lower() for kw in keywords.split(',') if kw.strip()] if keywords else []
    try:
        print(f"Analyse de l'URL : {url}")
        paragraphs_data = extract_paragraphs_from_url(url)
        if annee:
            paragraphs_data = [p for p in paragraphs_data if isinstance(p['date'], datetime) and p['date'].year == annee]

        for p_data in paragraphs_data:
            for keyword in keywords_list:
                if keyword in p_data['texte'].lower():
                    resultat[keyword].append(p_data)

        links = extract_links_from_url(url)
        for link in links:
            paragraphs_data = extract_paragraphs_from_url(link)
            if annee:
                paragraphs_data = [p for p in paragraphs_data if isinstance(p['date'], datetime) and p['date'].year == annee]

            for p_data in paragraphs_data:
                for keyword in keywords_list:
                    if keyword in p_data['texte'].lower():
                        resultat[keyword].append(p_data)

    except requests.exceptions.RequestException as e:
        return {"error": f"Erreur lors de l'accès à l'URL {url}: {e}"}
    except Exception as e:
        return {"error": f"Erreur inattendue lors de l'analyse de {url}: {e}"}
    return dict(resultat)

def extraction_du_texte(fichier):
    extension = os.path.splitext(fichier)[1].lower()
    text = ""
    try:
        if extension == ".pdf":
            with open(fichier, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        elif extension == ".docx":
            doc = docx.Document(fichier)
            for para in doc.paragraphs:
                text += para.text + "\n"
        elif extension == ".txt":
            with open(fichier, "r", encoding="utf-8") as f:
                text = f.read()
        else:
            print("Format de fichier non supporté.")
            return None
    except Exception as e:
        print(f"Erreur lors de l'extraction du texte depuis {fichier}: {e}")
        return None
    return text

def division_en_phrases(text):
    if not text:
        return []
    sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    print(f"Nombre de phrases extraites: {len(sentences)}")  
    return sentences

def recherche_mots_cles(sentences, keywords):
    results = {}
    keywords_list = [kw.strip() for kw in keywords.split(',') if kw.strip()]
    for keyword in keywords_list:
        keyword_lower = keyword.lower()
        print(f"Recherche du mot-clé '{keyword_lower}' dans {len(sentences)} phrases")
        found = [{"texte": sentence} for sentence in sentences if keyword_lower in sentence.lower()]
        results[keyword] = found
    return results

def generate_graph(phrases, keywords):
    keywords_list = [kw.strip().lower() for kw in keywords.split(',') if kw.strip()]
    counts = {kw: 0 for kw in keywords_list}
    for phrase in phrases:
        lower_phrase = phrase.lower()
        for kw in keywords_list:
            counts[kw] += lower_phrase.count(kw)
    df = pd.DataFrame(list(counts.items()), columns=["Mot clé", "Fréquence"])
    if not df.empty:
        plt.figure(figsize=(8, 6))
        plt.bar(df["Mot clé"], df["Fréquence"], color="skyblue")
        plt.title("Fréquence des mots clés")
        plt.xlabel("Mot clé")
        plt.ylabel("Fréquence")
        img_path = os.path.join("static", "images")
        os.makedirs(img_path, exist_ok=True)
        graph_file = os.path.join(img_path, "graph.png")
        plt.savefig(graph_file)
        plt.close()
        return url_for("static", filename="images/graph.png")
    else:
        return None

from waitress import serve

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 10000))
    serve(app, host="0.0.0.0", port=PORT)
