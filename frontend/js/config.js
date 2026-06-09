/**
 * config.js
 * ─────────
 * Central configuration for the Botivate AI frontend.
 * API_BASE_URL is auto-detected based on the environment.
 */

function getApiBaseUrl() {
    const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

    if (isLocalhost) {
        return 'http://localhost:8000';
    }

    // In production, use relative URLs or the same domain
    const protocol = window.location.protocol;
    const hostname = window.location.hostname;
    const port = window.location.port ? ':' + window.location.port : '';

    return `${protocol}//${hostname}${port}`;
}

const CONFIG = {
    /**
     * Base URL of the FastAPI backend.
     * Auto-detects: localhost → http://localhost:8000, otherwise → same origin
     */
    API_BASE_URL: getApiBaseUrl(),

    /** Persona shown in the greeting message */
    DIRECTOR_NAME: "Satyendra",

    /**
     * How many past conversation turns to send with each request.
     * 1 turn = 1 human message + 1 AI message.
     */
    HISTORY_TURNS_TO_KEEP: 5,
};
