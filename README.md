# 📊 Prévisions Économiques Cameroun — Web App

Une application web interactive développée avec **Flask** pour collecter et analyser des informations économiques sur le Cameroun. Le projet combine web scraping, analyse documentaire (PDF/Word/texte) et recherche par mots-clés, dans le cadre de l'exploitation du Big Data pour l'analyse économique (DGEPIP/MINEPAT).

## 🧰 Technologies utilisées

- **Python / Flask** : Backend web
- **HTML / CSS (Bootstrap 4)** : Frontend responsive
- **JavaScript** : Interaction utilisateur
- **BeautifulSoup / Requests** : Web scraping
- **PyPDF2, pdfplumber, python-docx** : Extraction de texte depuis des documents
- **Pandas / Matplotlib** : Analyse et visualisation des résultats
- **SQLite** : Base de données (comptes utilisateurs, analyses, articles)
- **Jinja2** : Templates HTML dynamiques

## ⚙️ Fonctionnalités principales

- 🔐 Authentification des utilisateurs (inscription / connexion)
- 📄 Analyse de documents (PDF, Word, texte) par recherche de mots-clés
- 🌐 Web scraping de sites économiques (sites prédéfinis ou URL libre), avec filtre par année de publication
- 📈 Graphique de fréquence des mots-clés trouvés
- 📰 Actualités économiques : ajout d'articles (manuel ou pré-rempli automatiquement depuis une URL)
- 📬 Formulaire de contact

## 🚀 Lancer le projet localement

1. **Cloner le dépôt et se placer dans le dossier du projet :**

```bash
git clone <url-du-depot>
cd opesc_projet
```

2. **Créer un environnement virtuel et installer les dépendances :**

```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/macOS
pip install -r requirements.txt
```

3. **Lancer l'application :**

```bash
python app.py
```

L'application est ensuite accessible sur [http://127.0.0.1:5000](http://127.0.0.1:5000).

La base de données SQLite (`database.db`) et ses tables sont créées automatiquement au premier lancement.

## 🗂️ Structure du projet

- `app.py` : routes Flask et logique applicative
- `scraper.py` : web scraping (extraction de paragraphes, liens, aperçus d'articles)
- `utils.py` : extraction de texte (PDF/Word/txt), découpage en phrases, recherche de mots-clés, formatage des dates
- `graph.py` : génération du graphique de fréquence des mots-clés
- `database.py` / `shema.sql` : schéma et connexion SQLite
- `templates/` : pages HTML (Jinja2)
- `static/` : CSS, JS et images
