function changerOption() {
    var choix = document.getElementById('choix-analyse').value;
    if (choix === 'documents') {
        document.getElementById('form-documents').style.display = 'block';
        document.getElementById('form-sites').style.display = 'none';
    } else if (choix === 'sites') {
        document.getElementById('form-documents').style.display = 'none';
        document.getElementById('form-sites').style.display = 'block';
    }
}
document.addEventListener('DOMContentLoaded', function() {
    const analyseForm = document.getElementById('analyse-form');
    const lancerAnalyseBtn = document.getElementById('lancerAnalyseBtn');
    const loadingIndicator = document.getElementById('loadingIndicator');

    if (analyseForm) {
        analyseForm.addEventListener('submit', function() {
            lancerAnalyseBtn.disabled = true;
            lancerAnalyseBtn.textContent = "Analyse en cours...";
            loadingIndicator.style.display = 'block';
        });
    }
});
document.getElementById('analyse-form').addEventListener('submit', function(event) {
    event.preventDefault();  // Empêche l'envoi normal du formulaire

    var choix = document.getElementById('choix-analyse').value;
    var resultatsDiv = document.getElementById('resultats');

    if (choix === 'documents') {
        var documentFile = document.getElementById('document').files[0];
        var motsCles = document.getElementById('mots-cles').value;
        
        // Crée un FormData pour envoyer un fichier et des mots-clés
        var formData = new FormData();
        formData.append('document', documentFile);
        formData.append('motsCles', motsCles);

        // Envoie la requête pour l'analyse du document
        fetch('/analyser', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                resultatsDiv.innerHTML = "<h3>Erreur :</h3><pre>" + data.error + "</pre>";
            } else {
                resultatsDiv.innerHTML = "<h3>Résultats de l'analyse du document :</h3><pre>" + JSON.stringify(data, null, 2) + "</pre>";
            }
        })
        .catch(error => {
            resultatsDiv.innerHTML = "<h3>Erreur :</h3><pre>" + error + "</pre>";
        });

    } else if (choix === 'sites') {
        var site = document.getElementById('site').value;
        var motsCles = document.getElementById('motsCles').value;

        // Envoie l'URL du site et les mots-clés au serveur pour analyse
        fetch('/analyser', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ site: site, motsCles: motsCles })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                resultatsDiv.innerHTML = "<h3>Erreur :</h3><pre>" + data.error + "</pre>";
            } else {
                resultatsDiv.innerHTML = "<h3>Résultats de l'analyse du site :</h3>" + data.resultats_html;
            }
        })
        .catch(error => {
            resultatsDiv.innerHTML = "<h3>Erreur :</h3><pre>" + error + "</pre>";
        });
    }

});
