// Fonction de basculement entre formulaire de document et site
function showForm(mode) {
    const formDocs = document.getElementById('form-documents');
    const formSites = document.getElementById('form-sites');
    document.getElementById('mode').value = mode;
    if(mode === 'document') {
        formDocs.style.display = 'block';
        formSites.style.display = 'none';
    } else {
        formDocs.style.display = 'none';
        formSites.style.display = 'block';
        document.getElementById('annee').setAttribute('required', 'required')
    }
}
// Au chargement, on affiche le formulaire de document par défaut
document.addEventListener('DOMContentLoaded', function() {
    showForm('document');
    const analyseForm = document.getElementById('analyse-form');
    const lancerAnalyseBtn = document.getElementById('lancerAnalyseBtn');
    const loadingIndicator = document.getElementById('loadingIndicator');
    analyseForm.addEventListener('submit', function(e) {
          // Optionnel: vous pouvez ajouter une vérification côté client ici
        lancerAnalyseBtn.disabled = true;
        lancerAnalyseBtn.textContent = "Analyse en cours...";
        loadingIndicator.style.display = 'block';
    });
});
  