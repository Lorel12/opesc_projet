document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-password-toggle]').forEach(function (toggle) {
        const password = document.getElementById(toggle.dataset.passwordToggle);
        const icon = toggle.querySelector('i');

        if (!password || !icon) {
            return;
        }

        toggle.addEventListener('click', function () {
            const isVisible = password.type === 'text';
            password.type = isVisible ? 'password' : 'text';
            toggle.setAttribute('aria-pressed', String(!isVisible));
            toggle.setAttribute('aria-label', isVisible ? 'Afficher le mot de passe' : 'Masquer le mot de passe');
            icon.classList.toggle('fa-eye', isVisible);
            icon.classList.toggle('fa-eye-slash', !isVisible);
        });
    });
});
