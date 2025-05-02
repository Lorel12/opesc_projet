(function() {
    emailjs.init("FLp5p7KTrNtSh3aXR_caV");
})();

function validate() {
    var prenom = document.getElementById('surname').value;
    var nom = document.getElementById('nom').value;
    var societe = document.getElementById('societe').value;
    var fonction = document.getElementById('fonction').value;
    var email = document.getElementById('email').value;
    var tel = document.getElementById('phone').value;
    var msg = document.getElementById('message').value;

    var verification_nbre = /\d/;
    if (prenom == "" || verification_nbre.test(prenom)){
        document.getElementById('errorsurname').innerHTML="Veuillez entrez un prenom valide";
        document.getElementById('surname').focus();
        return false;
    }else{
        document.getElementById('errorsurname').innerHTML="";
    }

    if (nom == "" || verification_nbre.test(nom)){
        document.getElementById('errorname').innerHTML="Veuillez entrez un nom valide";
        document.getElementById('nom').focus();
        return false;
    }else{
        document.getElementById('errorname').innerHTML="";
    }

    if (email == ""){
        document.getElementById('erroremail').innerHTML="Veuillez entrez un email valide";
        document.getElementById('email').focus();
        return false;
    }else{
        document.getElementById('erroremail').innerHTML="";
    }

    if (tel == ""){
        document.getElementById('errorphone').innerHTML="Veuillez entrez un numero valide (chiffres uniquement)";
        document.getElementById('phone').focus();
        return false;
    }else{
        document.getElementById('errorphone').innerHTML="";
    }

    if (msg == "") {
        document.getElementById('errormsg').innerHTML="Veuillez entrez un message";
        document.getElementById('message').focus();
        return false;
    } else {
        document.getElementById('errormsg').innerHTML="";
    }

    return true;
}

document.getElementById('contact-form').addEventListener('submit', function(event) {
    event.preventDefault(); // Empêche le rechargement de la page

    if (!validate()) {
        return; // Arrête la soumission si la validation échoue
    }

    // Récupère les valeurs du formulaire
    var templateParams = {
        surname: document.getElementById('surname').value, // Ajout du prénom
        name: document.getElementById('nom').value,
        fonction: document.getElementById('fonction').value, // Ajout de la fonction
        societe: document.getElementById('societe').value, // Ajout de la société
        email: document.getElementById('email').value,
        phone: document.getElementById('phone').value, // Ajout du téléphone
        message: document.getElementById('message').value
    };

    // Envoie l'email via EmailJS
    emailjs.send('service_9g5a8ss', 'template_9kk93bl', templateParams)
        .then(function(response) {
            console.log('SUCCESS!', response.status, response.text);
            alert('Votre message a été envoyé avec succès!');
            document.getElementById('contact-form').reset(); // Réinitialise le formulaire après l'envoi
        }, function(error) {
            console.log('FAILED...', error);
            alert('Une erreur est survenue, veuillez réessayer.');
        });
});
