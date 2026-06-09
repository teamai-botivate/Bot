/**
 * config.js
 * ─────────
 * Central configuration for the Botivate AI frontend.
 * Frontend and Backend run on the SAME PORT - relative URLs used.
 */

const CONFIG = {
    /**
     * Base URL of the FastAPI backend.
     * Uses relative URLs (same origin, same port).
     */
    API_BASE_URL: "",

    /** Persona shown in the greeting message */
    DIRECTOR_NAME: "Satyendra",

    /**
     * How many past conversation turns to send with each request.
     * 1 turn = 1 human message + 1 AI message.
     */
    HISTORY_TURNS_TO_KEEP: 5,
};
