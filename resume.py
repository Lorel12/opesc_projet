import os
import requests

# Étape 3 du TDR : résumé automatique orienté décision, via l'API gratuite
# Google Gemini (clé à obtenir sur https://aistudio.google.com, à définir
# dans la variable d'environnement GEMINI_API_KEY).
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
MAX_CORPUS_CHARS = 80000
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

def generer_resume(paragraphes, mots_cles):
    """Génère une synthèse en français à partir d'une liste de textes trouvés.

    Retourne {'resume': str} ou {'error': str}.
    """
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        return {"error": "Clé API Gemini manquante. Définissez la variable d'environnement GEMINI_API_KEY."}

    textes = [p for p in paragraphes if p and p.strip()]
    if not textes:
        return {"error": "Aucun paragraphe à résumer."}

    corpus = "\n\n".join(textes)
    if len(corpus) > MAX_CORPUS_CHARS:
        corpus = corpus[:MAX_CORPUS_CHARS]

    prompt = (
        "Tu es un analyste économique appuyant une direction de la planification publique. "
        f"À partir des extraits ci-dessous, en lien avec les mots-clés « {mots_cles} », rédige "
        "une synthèse claire et structurée en français, destinée à des décideurs publics. "
        "Présente les points clés sous forme de puces courtes, sans inventer d'information "
        "absente des extraits, et indique s'ils se contredisent ou restent incomplets sur un point.\n\n"
        "Extraits :\n" + corpus
    )

    try:
        response = requests.post(
            GEMINI_API_URL,
            params={"key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=60
        )
        response.raise_for_status()
        data = response.json()
        texte = data["candidates"][0]["content"]["parts"][0]["text"]
        return {"resume": texte.strip()}
    except requests.exceptions.RequestException as e:
        return {"error": f"Erreur d'appel à l'API Gemini : {e}"}
    except (KeyError, IndexError):
        return {"error": "Réponse inattendue de l'API Gemini."}
