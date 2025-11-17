// Shared JavaScript utilities for test pages

// API base URL
const API_BASE = '/api/v1';

// Helper function for API calls
async function apiCall(endpoint, options = {}) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
        headers: {
            'Content-Type': 'application/json',
            ...options.headers,
        },
        ...options,
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(error.detail || 'API request failed');
    }

    return response.json();
}

// WebSocket helper
function createWebSocket(url, onMessage, onError, onClose) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}${url}`);

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            onMessage(data);
        } catch (e) {
            console.error('Failed to parse WebSocket message:', e);
        }
    };

    ws.onerror = onError || (() => console.error('WebSocket error'));
    ws.onclose = onClose || (() => console.log('WebSocket closed'));

    return ws;
}

// Format date helper
function formatDate(dateString) {
    return new Date(dateString).toLocaleString();
}

// Format currency helper
function formatCurrency(amount) {
    return `$${amount.toFixed(4)}`;
}

