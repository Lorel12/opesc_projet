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

import urllib.robotparser
from urllib.parse import urlparse

# User-Agent utilisé pour éviter les blocages par certains sites
user_agent = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
headers = {"User-Agent": user_agent}

# Cache pour stocker les robotparser par domaine
robots_parsers = {}

def get_robots_parser(base_url):
    """Récupère et met en cache le parser robots.txt pour un domaine donné"""
    parsed_url = urlparse(base_url)
    if not parsed_url.netloc:  # Vérifie qu'on a bien un domaine valide
        print(f"[Erreur] URL malformée ignorée : {base_url}")
        return None
    base = f"{parsed_url.scheme}://{parsed_url.netloc}"
    if base not in robots_parsers:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(base + "/robots.txt")
        try:
            rp.read()
        except Exception as e:
            print(f"[Erreur] Impossible de lire robots.txt pour {base} : {e}")
            # En cas d'erreur, on autorise par défaut
            rp = None
        robots_parsers[base] = rp
    return robots_parsers[base]

def can_scrape(url):
    """Vérifie si l'URL peut être scrappée selon robots.txt"""
    parsed_url = urlparse(url)
    base = f"{parsed_url.scheme}://{parsed_url.netloc}"
    rp = get_robots_parser(base)
    if rp is None:
        # Si on n'a pas pu charger robots.txt, on autorise pour ne pas bloquer
        return True
    return rp.can_fetch(user_agent, url)

def extract_published_date(soup):
    """Tente de récupérer la date de publication d'une page depuis ses balises meta/time."""
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
            return parser.parse(date_str)
        return None
    except Exception as ex:
        print(f"[Erreur date] Conversion échouée : '{date_str}' — {ex}")
        return None


def extract_paragraphs_from_url(url):
    if not can_scrape(url):
        print(f"[robots.txt] Scraping interdit pour {url}")
        return []  # On ne scrape pas les URL interdites

    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()

        content_type = response.headers.get('Content-Type', '')
        if 'html' not in content_type:
            print(f"[Info] URL non HTML ignorée : {url} (Content-Type: {content_type})")
            return []

        try:
            soup = BeautifulSoup(response.content, 'html.parser')

        except Exception as e:
            print(f"[Erreur parsing HTML] {url} : {e}")
            return []

        paragraphs_data = []

        date_obj = extract_published_date(soup)

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

from urllib.parse import urlparse, urljoin

def extract_links_from_url(url):
    if not can_scrape(url):
        print(f"[robots.txt] Extraction de liens interdite pour {url}")
        return []

    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        links = set()

        for link in soup.find_all('a', href=True):
            href = link['href'].strip()

            if href.startswith(('javascript:', 'mailto:', '#')) or not href:
                continue

            full_url = urljoin(url, href)

            parsed = urlparse(full_url)
            if not parsed.scheme.startswith('http') or not parsed.netloc:
                print(f"[Lien ignoré] URL invalide ou locale : {href} → {full_url}")
                continue

            if can_scrape(full_url):
                links.add(full_url)

        return list(links)

    except requests.exceptions.RequestException as e:
        print(f"[Erreur récupération liens] {url} — {e}")
        return []



def analyse_site(url, keywords, annee=None):
    resultat = defaultdict(list)
    keywords_list = [kw.strip().lower() for kw in keywords.split(',') if kw.strip()] if keywords else []

    try:
        print(f"[Analyse] URL principale : {url}")

        def process_paragraphs(paragraphs_data, source_url):
            for p_data in paragraphs_data:
                texte = p_data.get('texte', '')
                if annee:
                    date = p_data.get('date')
                    if isinstance(date, datetime):
                        if date.year != annee:
                            continue
                    else:
                        continue  # Année demandée mais date invalide
                for keyword in keywords_list:
                    if re.search(rf'\b{re.escape(keyword)}\b', texte, re.IGNORECASE):
                        p_data.setdefault('source', source_url)
                        p_data.setdefault('date', None)
                        resultat[keyword].append(p_data)

        # Traitement de la page principale
        main_paragraphs = extract_paragraphs_from_url(url)
        process_paragraphs(main_paragraphs, url)

        # Traitement des 10 premiers liens internes
        links = extract_links_from_url(url)
        for link in links: #[:20]:
            link_paragraphs = extract_paragraphs_from_url(link)
            process_paragraphs(link_paragraphs, link)

    except requests.exceptions.RequestException as e:
        return {"error": f"Erreur d'accès à l'URL {url} : {e}"}
    except Exception as e:
        return {"error": f"Erreur inattendue lors de l'analyse de {url} : {e}"}

    return dict(resultat)


def extract_article_preview(url):
    """Récupère titre, extrait, image et date de publication d'une page pour alimenter les Actualités."""
    if not can_scrape(url):
        return {"error": f"Le scraping de {url} est interdit par robots.txt."}

    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()

        content_type = response.headers.get('Content-Type', '')
        if 'html' not in content_type:
            return {"error": f"URL non HTML : {url}"}

        soup = BeautifulSoup(response.content, 'html.parser')

        titre_tag = soup.find('meta', {'property': 'og:title'})
        if titre_tag and titre_tag.get('content'):
            titre = titre_tag['content'].strip()
        elif soup.title and soup.title.string:
            titre = soup.title.string.strip()
        else:
            titre = url

        contenu = ""
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            if len(text) > 80:
                contenu = text
                break

        image_tag = soup.find('meta', {'property': 'og:image'})
        if image_tag and image_tag.get('content'):
            image_url = urljoin(url, image_tag['content'])
        else:
            img_tag = soup.find('img')
            image_url = urljoin(url, img_tag['src']) if img_tag and img_tag.get('src') else None

        date_obj = extract_published_date(soup)

        return {
            'titre': titre,
            'contenu': contenu,
            'image_url': image_url,
            'date_publication': date_obj,
            'url': url,
        }

    except requests.exceptions.RequestException as e:
        return {"error": f"Erreur d'accès à l'URL {url} : {e}"}
