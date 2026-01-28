const urlParams = new URLSearchParams(window.location.search);
const peer = urlParams.get('peer');
let myClientId = null;

if (!peer) {
    window.location.href = '/';
}

document.getElementById('peerName').textContent = peer;

async function getStatus() {
    const res = await fetch('/status');
    const data = await res.json();
    myClientId = data.client_id;
}

async function loadMessages() {
    const res = await fetch(`/messages/${peer}`);
    const messages = await res.json();
    const chatBox = document.getElementById('chatBox');

    if (messages.length === 0) {
        chatBox.innerHTML = '<div class="no-messages">Aucun message. Commencez la conversation !</div>';
        return;
    }

    chatBox.innerHTML = messages.map(msg => {
        if (msg.from === 'SYSTEM') {
            return `<div class="message system">${msg.message}</div>`;
        }

        const isSent = msg.from === myClientId;
        const verifiedClass = msg.verified ? 'ok' : 'notok';
        const verifiedText = msg.verified ? '[OK]' : '[NOTOK]';

        return `
            <div class="message ${isSent ? 'sent' : 'received'}">
                <div class="message-content">${escapeHtml(msg.message)}</div>
                <div class="message-meta">
                    <span class="verified ${verifiedClass}">${verifiedText}</span>
                    <span>${msg.timestamp}</span>
                </div>
            </div>
        `;
    }).join('');

    // Scroll vers le bas
    chatBox.scrollTop = chatBox.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();

    if (!message) return;

    const sendBtn = document.getElementById('sendBtn');
    sendBtn.disabled = true;

    try {
        const res = await fetch('/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message, peer: peer })
        });

        if (res.ok) {
            input.value = '';
            await loadMessages();
        } else {
            alert('Erreur lors de l\'envoi du message');
        }
    } catch (error) {
        alert('Erreur de connexion');
    }

    sendBtn.disabled = false;
    input.focus();
}

function handleKeyPress(event) {
    if (event.key === 'Enter') {
        sendMessage();
    }
}

function goBack() {
    window.location.href = '/';
}

// Initialisation
async function init() {
    await getStatus();
    await loadMessages();
}

init();

// Actualise les messages toutes les 2 secondes
setInterval(loadMessages, 2000);