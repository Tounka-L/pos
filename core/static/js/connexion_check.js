window.addEventListener('online', () => {
    console.log("Connexion rétablie !");
    document.body.style.borderTop = "none";
    alert("Vous êtes de nouveau en ligne. Les données vont se synchroniser.");
});

window.addEventListener('offline', () => {
    console.log("Connexion perdue...");
    // Optionnel : ajouter une barre rouge discrète en haut du site
    document.body.style.borderTop = "5px solid red";
    alert("Attention : Vous travaillez actuellement hors-ligne.");
});