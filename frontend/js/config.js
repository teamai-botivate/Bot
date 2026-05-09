/**
 * config.js
 * ─────────
 * Central configuration for the Botivate AI frontend.
 * Change API_BASE_URL to point at your backend when deploying.
 */

const CONFIG = {
    /**
     * Base URL of the FastAPI backend.
     * - Local dev  : "http://localhost:8000"
     * - Production : "https://your-backend-domain.com"
     */
    API_BASE_URL: "http://localhost:8000",

    /** Persona shown in the greeting message */
    DIRECTOR_NAME: "Satyendra",

    /**
     * How many past conversation turns to send with each request.
     * 1 turn = 1 human message + 1 AI message.
     */
    HISTORY_TURNS_TO_KEEP: 5,
};
