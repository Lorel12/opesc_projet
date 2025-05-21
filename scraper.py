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

def extract_paragraphs_from_url(url):
    try:
        response = requests.get(url, timeout=20)
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
        response = requests.get(url, headers=headers, timeout=30)
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
    from collections import defaultdict
    from datetime import datetime

    resultat = defaultdict(list)
    keywords_list = [kw.strip().lower() for kw in keywords.split(',') if kw.strip()] if keywords else []

    try:
        print(f"Analyse de l'URL : {url}")
        def process_paragraphs(paragraphs_data, source_url):
            for p_data in paragraphs_data:
                texte = p_data.get('texte', '').lower()
                if annee:
                    date = p_data.get('date')
                    if not (isinstance(date, datetime) and date.year == annee):
                        continue
                for keyword in keywords_list:
                    if keyword in texte:
                        p_data.setdefault('source', source_url)
                        p_data.setdefault('date', None)
                        resultat[keyword].append(p_data)

        main_paragraphs = extract_paragraphs_from_url(url)
        process_paragraphs(main_paragraphs, url)

        links = extract_links_from_url(url)
        for link in links[:10]:
            link_paragraphs = extract_paragraphs_from_url(link)
            process_paragraphs(link_paragraphs, link)

    except requests.exceptions.RequestException as e:
        return {"error": f"Erreur lors de l'accès à l'URL {url}: {e}"}
    except Exception as e:
        return {"error": f"Erreur inattendue lors de l'analyse de {url}: {e}"}
    
    return dict(resultat)
