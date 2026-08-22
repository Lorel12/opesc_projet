from flask import Flask, render_template, request, redirect, url_for, session, flash
import hashlib
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Important pour Render ou tout serveur sans interface graphique
import matplotlib.pyplot as plt
import docx
from collections import defaultdict
import os, json, sqlite3, logging
from werkzeug.utils import secure_filename
from datetime import datetime
from dateutil import parser
import pdfplumber
from markupsafe import Markup, escape

# Configuration du logger
logging.basicConfig(filename='logs.txt', level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')

# User-Agent pour le scraping web
user_agent = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
headers = {"User-Agent": user_agent}

# 🔍 Fonction 1 : Extraction de texte depuis différents formats
def extraction_du_texte(fichier):
    extension = os.path.splitext(fichier)[1].lower()
    text = ""

    # ✅ Limitation de la taille du fichier (5 Mo)
    MAX_FILE_SIZE_MB = 5
    if os.path.getsize(fichier) > MAX_FILE_SIZE_MB * 1024 * 1024:
        logging.warning(f"Fichier trop volumineux : {fichier}")
        return None

    try:
        if extension == ".pdf":
            with pdfplumber.open(fichier) as pdf:
                max_pages = 5  # Pour limiter les ressources sur Render
                for i, page in enumerate(pdf.pages[:max_pages]):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                    except Exception as e:
                        logging.error(f"[Erreur PDF page {i}] {e}")
                        continue

        elif extension == ".docx":
            doc = docx.Document(fichier)
            for para in doc.paragraphs:
                text += para.text + "\n"

        elif extension == ".txt":
            with open(fichier, "r", encoding="utf-8") as f:
                text = f.read()

        else:
            logging.warning(f"❌ Format non supporté : {extension}")
            return None

    except Exception as e:
        logging.error(f"[Erreur extraction globale] {e}")
        return None

    return text

# ✂️ Fonction 2 : Découpe le texte en phrases
def division_en_phrases(text):
    if not text:
        return []
    sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    logging.info(f"[Division] Nombre de phrases extraites : {len(sentences)}")
    return sentences

# 🧠 Fonction 3 : Recherche de mots-clés dans les phrases
def recherche_mots_cles(sentences, keywords):
    results = {}
    keywords_list = [kw.strip() for kw in keywords.split(',') if kw.strip()]
    now = datetime.now().isoformat()

    for keyword in keywords_list:
        keyword_lower = keyword.lower()
        logging.info(f"[Recherche] Mot-clé '{keyword_lower}' dans {len(sentences)} phrases...")

        # Recherche avec mot complet uniquement (expression régulière)
        found = []
        for sentence in sentences:
            if re.search(rf'\b{re.escape(keyword_lower)}\b', sentence, re.IGNORECASE):
                found.append({
                    "texte": sentence,
                    "date": now,
                    "keyword": keyword
                })
        results[keyword] = found

    return results

# 📅 Fonction 4 : Formatage d'une date (str ISO ou datetime) pour l'affichage
def format_display_date(value):
    if value is None:
        return "Date inconnue"
    if isinstance(value, datetime):
        return value.strftime('%d/%m/%Y %H:%M')
    if isinstance(value, str):
        if value == "Date inconnue" or not value.strip():
            return "Date inconnue"
        try:
            return datetime.fromisoformat(value).strftime('%d/%m/%Y %H:%M')
        except ValueError:
            return value
    return "Date inconnue"

# ✨ Fonction 5 : Rendu léger et sûr du Markdown renvoyé par l'IA (gras, puces)
def rendre_markdown_leger(texte):
    """Convertit le sous-ensemble Markdown produit par l'IA (gras, listes à puces)
    en HTML minimal. Le texte est échappé avant toute insertion de balise, donc
    aucun contenu du texte source (y compris du HTML) ne peut être interprété."""
    if not texte:
        return Markup("")

    def appliquer_gras(ligne_echappee):
        return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', ligne_echappee)

    html_parts = []
    paragraph_lines = []
    in_list = False

    def flush_paragraph():
        if paragraph_lines:
            contenu = " ".join(paragraph_lines).strip()
            if contenu:
                html_parts.append("<p>%s</p>" % appliquer_gras(contenu))
            paragraph_lines.clear()

    for ligne in str(texte).split("\n"):
        ligne_echappee = str(escape(ligne.strip()))
        if not ligne_echappee:
            flush_paragraph()
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            continue

        m = re.match(r'^[\*\-]\s+(.*)', ligne_echappee)
        if m:
            flush_paragraph()
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            html_parts.append("<li>%s</li>" % appliquer_gras(m.group(1)))
        else:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            paragraph_lines.append(ligne_echappee)

    flush_paragraph()
    if in_list:
        html_parts.append("</ul>")

    return Markup("".join(html_parts))
