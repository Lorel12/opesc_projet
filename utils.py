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
import os, json, sqlite3
from werkzeug.utils import secure_filename
from datetime import datetime
from dateutil import parser
import pdfplumber

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
                        print(f"[Erreur PDF page {i}] {e}")
                        continue

        elif extension == ".docx":
            doc = docx.Document(fichier)
            for para in doc.paragraphs:
                text += para.text + "\n"

        elif extension == ".txt":
            with open(fichier, "r", encoding="utf-8") as f:
                text = f.read()

        else:
            print("❌ Format non supporté :", extension)
            return None

    except Exception as e:
        print(f"[Erreur extraction globale] {e}")
        return None

    return text


# ✂️ Fonction 2 : Découpe le texte en phrases
def division_en_phrases(text):
    if not text:
        return []
    sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    print(f"[Division] Nombre de phrases extraites : {len(sentences)}")
    return sentences


# 🧠 Fonction 3 : Recherche de mots-clés dans les phrases
def recherche_mots_cles(sentences, keywords):
    results = {}
    keywords_list = [kw.strip() for kw in keywords.split(',') if kw.strip()]
    for keyword in keywords_list:
        keyword_lower = keyword.lower()
        print(f"[Recherche] Mot-clé '{keyword_lower}' dans {len(sentences)} phrases...")
        found = [{"texte": sentence} for sentence in sentences if keyword_lower in sentence.lower()]
        results[keyword] = found
    return results
