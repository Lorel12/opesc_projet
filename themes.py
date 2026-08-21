import re

# Dictionnaire thème -> mots-clés/expressions associés (Étape 2 du TDR :
# classification thématique légère, sans modèle NLP lourd type spaCy/BERT).
THEMES = {
    "Croissance": [
        "croissance", "pib", "produit intérieur brut", "récession",
        "expansion économique", "ralentissement économique", "reprise économique",
    ],
    "Emploi": [
        "emploi", "chômage", "recrutement", "licenciement", "marché du travail",
        "main-d'œuvre", "main d'œuvre", "travailleur", "travailleurs", "insertion professionnelle",
    ],
    "Inflation": [
        "inflation", "déflation", "pouvoir d'achat", "indice des prix", "hausse des prix",
        "coût de la vie",
    ],
    "Fiscalité": [
        "impôt", "impôts", "taxe", "taxes", "fiscalité", "tva", "douane", "douanes",
        "recette fiscale", "recettes fiscales", "exonération",
    ],
    "Finances publiques": [
        "budget", "dette publique", "déficit", "dépenses publiques", "loi de finances",
        "trésor public", "endettement",
    ],
    "Commerce extérieur": [
        "exportation", "exportations", "importation", "importations", "commerce extérieur",
        "balance commerciale", "échanges commerciaux",
    ],
    "Investissement": [
        "investissement", "investissements", "investisseur", "investisseurs",
        "ide", "capital", "capitaux",
    ],
    "Monnaie et change": [
        "franc cfa", "taux de change", "devise", "devises", "monnaie", "dépréciation",
        "appréciation monétaire",
    ],
    "Secteur agricole": [
        "agriculture", "agricole", "agricoles", "exploitation agricole", "récolte",
        "filière agricole", "agro-industrie",
    ],
    "Secteur industriel": [
        "industrie", "industriel", "industrielle", "production industrielle", "usine", "usines",
    ],
    "Énergie": [
        "énergie", "électricité", "pétrole", "hydrocarbures", "gaz naturel", "barrage hydroélectrique",
    ],
    "Social": [
        "pauvreté", "social", "développement social", "inégalité", "inégalités",
        "protection sociale", "précarité",
    ],
}


def identifier_themes(texte):
    """Retourne la liste des thèmes économiques détectés dans un texte donné."""
    if not texte:
        return []

    themes_trouves = []
    for theme, mots_cles in THEMES.items():
        for mot_cle in mots_cles:
            if re.search(rf'\b{re.escape(mot_cle)}\b', texte, re.IGNORECASE):
                themes_trouves.append(theme)
                break

    return themes_trouves
