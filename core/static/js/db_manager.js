// --- CONFIGURATION DE LA BASE DE DONNÉES ---
const db = new Dexie("RBA_POS_DB");

// Définition des tables
// ++id : Clé primaire auto-incrémentée
// sync : Indexé pour des recherches rapides (0 = non sync, 1 = sync)
db.version(1).stores({
    ventes: '++id, date, client, total, sync',
    produits: 'id, nom, prix'
});

// Ouverture de la base
db.open().then(() => {
    console.log("IndexedDB RBA : Base de données ouverte avec succès !");
}).catch((err) => {
    console.error("Erreur IndexedDB : " + err.stack);
});

// --- UTILITAIRES ---

// Fonction pour récupérer le token CSRF nécessaire pour les requêtes POST Django
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// --- SYNCHRONISATION ---

// Envoyer une seule vente au serveur
async function envoyerVenteAuServeur(vente) {
    try {
        const response = await fetch('/sync-vente/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify(vente)
        });

        const result = await response.json();

        if (response.ok && result.status === 'success') {
            // Mise à jour locale : on marque comme synchronisé
            await db.ventes.update(vente.id, { sync: 1 });
            console.log(`✅ Vente #${vente.id} synchronisée avec le serveur Django.`);
        } else {
            console.error(`⚠️ Erreur serveur pour la vente #${vente.id}:`, result.message);
        }
    } catch (error) {
        console.error("❌ Erreur réseau lors de la synchro :", error);
    }
}

// Chercher et envoyer toutes les ventes en attente (sync = 0)
async function synchroniserTout() {
    if (!navigator.onLine) {
        console.log("Hors-ligne : Synchronisation reportée.");
        return;
    }

    const ventesNonSync = await db.ventes.where('sync').equals(0).toArray();
    
    if (ventesNonSync.length > 0) {
        console.log(`🔄 Synchro de ${ventesNonSync.length} ventes en cours...`);
        for (let vente of ventesNonSync) {
            await envoyerVenteAuServeur(vente);
        }
    } else {
        console.log("✨ Tout est à jour. Aucune vente à synchroniser.");
    }
}

// --- ÉVÉNEMENTS ---

// Déclencher la synchro quand la connexion revient
window.addEventListener('online', () => {
    console.log("🌐 Connexion rétablie !");
    synchroniserTout();
});

// Vérifier au chargement si des données attendent
window.addEventListener('load', synchroniserTout);