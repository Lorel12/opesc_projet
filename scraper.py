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

# User-Agent utilisé pour éviter les blocages par certains sites
user_agent = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
headers = {"User-Agent": user_agent}


# 🔍 Fonction : Extraire les paragraphes d’un article à une URL donnée
def extract_paragraphs_from_url(url):
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        paragraphs_data = []

        # Tentative de récupération de la date de publication
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
                if re.match(r'^\d{4}-\d{2}-\d{2}\d{2}:\d{2}:\d{2}', date_str):
                    date_str = date_str[:10] + 'T' + date_str[10:]
                date_obj = parser.parse(date_str)
            else:
                date_obj = None
        except Exception as ex:
            print(f"[Erreur date] Conversion échouée : '{date_str}' — {ex}")
            date_obj = None

        # Extraction des paragraphes
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
        print(f"[Erreur réseau] URL : {url} — {e}")
        return []


# 🌐 Fonction : Extraire les liens internes valides depuis une page
def extract_links_from_url(url):
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        links = set()
        for link in soup.find_all('a', href=True):
            href = link['href'].strip()
            if href.startswith("javascript:") or href.startswith("mailto:") or href in ['#', '']:
                continue
            full_url = urljoin(url, href)
            links.add(full_url)
        return list(links)
    except requests.exceptions.RequestException as e:
        print(f"[Erreur récupération liens] {url} — {e}")
        return []


# 🧠 Fonction principale : Analyse d’un site avec mots-clés et filtre par année
def analyse_site(url, keywords, annee=None):
    resultat = defaultdict(list)
    keywords_list = [kw.strip().lower() for kw in keywords.split(',') if kw.strip()] if keywords else []

    try:
        print(f"[Analyse] URL principale : {url}")

        def process_paragraphs(paragraphs_data, source_url):
            for p_data in paragraphs_data:
                texte = p_data.get('texte', '').lower()
                if annee:
                    date = p_data.get('date')
                    if isinstance(date, datetime):
                        if date.year != annee:
                            continue
                    else:
                        continue  # Année demandée mais date invalide
                for keyword in keywords_list:
                    if keyword in texte:
                        p_data.setdefault('source', source_url)
                        p_data.setdefault('date', None)
                        resultat[keyword].append(p_data)

        # Traitement de la page principale
        main_paragraphs = extract_paragraphs_from_url(url)
        process_paragraphs(main_paragraphs, url)

        # Traitement des 10 premiers liens internes
        links = extract_links_from_url(url)
        for link in links[:10]:
            link_paragraphs = extract_paragraphs_from_url(link)
            process_paragraphs(link_paragraphs, link)

    except requests.exceptions.RequestException as e:
        return {"error": f"Erreur d'accès à l'URL {url} : {e}"}
    except Exception as e:
        return {"error": f"Erreur inattendue lors de l'analyse de {url} : {e}"}

    return dict(resultat)
