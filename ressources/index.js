let myClientId = null;
let activeSessions = [];

async function getStatus() {
    const res = await fetch('/status');
    const data = await res.json();
    myClientId = data.client_id;
    activeSessions = data.sessions || [];
    document.getElementById('myClientId').textContent = myClientId;
}

async function loadClients() {
    await getStatus();

    const res = await fetch('/clients');
    const data = await res.json();
    const clientList = document.getElementById('clientList');

    const otherClients = data.clients.filter(c => c.client_id !== myClientId);

    if (otherClients.length === 0) {
        clientList.innerHTML = '<div class="no-clients">Aucun autre client connecté</div>';
        return;
    }

    clientList.innerHTML = otherClients.map(client => {
        const hasSession = activeSessions.includes(client.client_id);
        return `
            <div class="client-card ${hasSession ? 'has-session' : ''}"
                 onclick="selectClient('${client.client_id}')">
                <div class="client-info">
                    <div class="client-name">${client.client_id}</div>
                    <div class="client-address">${client.address}</div>
                </div>
                <span class="client-status ${hasSession ? 'status-connected' : 'status-available'}">
                    ${hasSession ? 'Connecté' : 'Disponible'}
                </span>
            </div>
        `;
    }).join('');
}

async function selectClient(clientId) {
    // Établit la connexion si pas de session
    if (!activeSessions.includes(clientId)) {
        const res = await fetch('/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ peer: clientId })
        });

        if (!res.ok) {
            alert('Erreur lors de la connexion');
            return;
        }
    }

    // Ouvre la page de chat
    window.location.href = `/chat?peer=${clientId}`;
}

// Charge les clients au démarrage
loadClients();

// Actualise toutes les 5 secondes
setInterval(loadClients, 5000);