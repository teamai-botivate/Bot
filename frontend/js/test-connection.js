/**
 * test-connection.js
 * ──────────────────
 * Utility to test frontend-backend connectivity.
 * Include this in your HTML for debugging.
 */

async function testBackendConnection() {
    console.log("🔍 Testing Botivate AI Backend Connection...");
    console.log(`📍 Frontend Origin: ${window.location.origin}`);
    console.log(`🎯 API Base URL: ${CONFIG.API_BASE_URL}`);

    try {
        // Test 1: Health Check
        console.log("\n[TEST 1] Checking /health endpoint...");
        const healthResponse = await fetch(`${CONFIG.API_BASE_URL}/health`);
        if (healthResponse.ok) {
            const healthData = await healthResponse.json();
            console.log("✅ Health check passed:", healthData);
        } else {
            console.error(`❌ Health check failed: ${healthResponse.status} ${healthResponse.statusText}`);
            return false;
        }

        // Test 2: Root endpoint
        console.log("\n[TEST 2] Checking root (/) endpoint...");
        const rootResponse = await fetch(`${CONFIG.API_BASE_URL}/`);
        if (rootResponse.ok) {
            console.log("✅ Root endpoint accessible");
        } else {
            console.error(`❌ Root endpoint failed: ${rootResponse.status}`);
        }

        // Test 3: Chat endpoint without data
        console.log("\n[TEST 3] Checking /chat endpoint (validation)...");
        const chatResponse = await fetch(`${CONFIG.API_BASE_URL}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question: "Hello",
                chat_history: []
            })
        });

        if (chatResponse.ok) {
            const chatData = await chatResponse.json();
            console.log("✅ Chat endpoint working:", chatData);
            return true;
        } else {
            console.error(`⚠️  Chat endpoint returned: ${chatResponse.status}`);
            const errorText = await chatResponse.text();
            console.error("Response:", errorText);
            return false;
        }

    } catch (error) {
        console.error("❌ Connection test failed:", error.message);
        console.error("\nPossible issues:");
        console.error("  • Backend is not running");
        console.error("  • API_BASE_URL is incorrect");
        console.error("  • CORS is not properly configured");
        console.error("  • Network connectivity issue");
        return false;
    }
}

// Auto-run on page load if in development
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    window.addEventListener('DOMContentLoaded', () => {
        console.log("\n" + "=".repeat(60));
        testBackendConnection().then(success => {
            console.log("\n" + "=".repeat(60));
            if (success) {
                console.log("✅ Connection test completed successfully!");
            } else {
                console.log("⚠️  Connection test encountered issues. See above for details.");
            }
        });
    });
}

// Make function globally available
window.testBackendConnection = testBackendConnection;
