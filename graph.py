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
import os, json, sqlite3, uuid
from werkzeug.utils import secure_filename
from datetime import datetime
from dateutil import parser

user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
headers = {"User-Agent": user_agent}

def generate_graph(phrases, keywords):
    keywords_list = [kw.strip().lower() for kw in keywords.split(',') if kw.strip()]
    counts = {kw: 0 for kw in keywords_list}
    for phrase in phrases:
        for kw in keywords_list:
            counts[kw] += len(re.findall(rf'\b{re.escape(kw)}\b', phrase, re.IGNORECASE))
    df = pd.DataFrame(list(counts.items()), columns=["Mot clé", "Fréquence"])
    if not df.empty:
        plt.figure(figsize=(8, 6))
        plt.bar(df["Mot clé"], df["Fréquence"], color="skyblue")
        plt.title("Fréquence des mots clés")
        plt.xlabel("Mot clé")
        plt.ylabel("Fréquence")
        img_path = os.path.join("static", "images")
        os.makedirs(img_path, exist_ok=True)
        filename = f"graph_{uuid.uuid4().hex[:12]}.png"
        graph_file = os.path.join(img_path, filename)
        plt.savefig(graph_file)
        plt.close()
        return url_for("static", filename=f"images/{filename}")
    else:
        return None
