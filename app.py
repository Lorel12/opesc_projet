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

user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
headers = {"User-Agent": user_agent}

app = Flask(__name__)
app.secret_key = 'your secret key'
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

DB_PATH = 'database.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        email TEXT,
        created_at TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        mots_cles TEXT,
        mode TEXT,
        resultats TEXT,
        graph_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')          
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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
""" 
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

    if 'last_analysis_id' in session:
    conn = get_db_connection()
    row = conn.execute('SELECT * FROM analyses WHERE id = ?', (session['last_analysis_id'],)).fetchone()
    conn.close()
    if row:
        resultats_analyse = json.loads(row['resultats'])
        mode = row['mode']
        mots_cles = row['mots_cles']
        graph_url = row['graph_url']


    if resultats_analyse is None:
        return render_template('resultats.html', error_message="Aucune analyse effectuée.")
    
    return render_template('resultats.html', resultats_analyse=resultats_analyse, mode=mode, mots_cles=mots_cles)
    """
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
            else:
                error_message = "Veuillez saisir une URL."        
        else:
            raise ValueError('Mode inconnu.')
    except Exception as e:
        error_message = str(e)
    # on sauvegarde
    if 'id' in session:
        conn = get_db_connection()
        cur = conn.execute(
            'INSERT INTO analyses (user_id, mots_cles, mode, resultats, graph_url) VALUES (?, ?, ?, ?, ?)',
            (session['id'], mots_cles, mode, json.dumps(analyse_result), graph_url)
        )
        session['last_analysis_id'] = cur.lastrowid
        conn.commit()
        conn.close()
    return render_template('resultats.html', resultats_analyse=analyse_result, mode=mode, mots_cles=mots_cles, graph_url=graph_url, error_message=error_message)

@app.route('/resultats')
def resultats():
    if 'last_analysis_id' in session:
        conn = get_db_connection()
        row = conn.execute('SELECT * FROM analyses WHERE id = ?', (session['last_analysis_id'],)).fetchone()
        conn.close()
        if row:
            resultats_analyse = json.loads(row['resultats'])
            mode = row['mode']
            mots_cles = row['mots_cles']
            graph_url = row['graph_url']
            return render_template('resultats.html', resultats_analyse=resultats_analyse, mode=mode, mots_cles=mots_cles, graph_url=graph_url)
    return render_template('resultats.html', error_message="Aucune analyse.")

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
                
                # 'T' entre la date et l'heure 
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
        #print(f"Erreur lors de l'extraction du texte depuis {fichier}: {e}")
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

if __name__ == "__main__":
    app.run(debug=True)
