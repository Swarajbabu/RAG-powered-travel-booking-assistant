const logger = require("../config/logger");

function parseHistory(history) {
    if (!Array.isArray(history)) {
        throw new Error("Chat history must be an array.");
    }

    return history.slice(-4).filter((turn) => (
        turn && typeof turn.role === "string" && typeof turn.content === "string"
    ));
}

async function sendMessage(req, res) {
    if (process.env.RAG_CHAT_ENABLED === "false") {
        return res.status(503).json({ error: "The travel assistant is temporarily unavailable." });
    }

    const message = typeof req.body?.message === "string" ? req.body.message.trim() : "";
    if (!message) {
        return res.status(400).json({ error: "Enter a message." });
    }
    if (message.length > 2000) {
        return res.status(400).json({ error: "The message must be 2000 characters or fewer." });
    }

    let history;
    try {
        history = parseHistory(req.body.history || []);
    } catch (error) {
        return res.status(400).json({ error: error.message });
    }

    const ragServiceUrl = process.env.RAG_SERVICE_URL;
    const ragServiceSecret = process.env.RAG_SERVICE_SECRET;
    if (!ragServiceUrl || !ragServiceSecret) {
        logger.error("RAG chat is missing RAG_SERVICE_URL or RAG_SERVICE_SECRET.");
        return res.status(503).json({ error: "The travel assistant is temporarily unavailable." });
    }

    const timeoutMs = Number.parseInt(process.env.RAG_REQUEST_TIMEOUT_MS || "30000", 10);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);

    try {
        const response = await fetch(`${ragServiceUrl.replace(/\/$/, "")}/chat`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-RAG-Service-Key": ragServiceSecret
            },
            body: JSON.stringify({
                question: message,
                history,
                pageContext: String(req.body.pageContext || req.originalUrl || "").slice(0, 500),
                language: "en"
            }),
            signal: controller.signal
        });

        const payload = await response.json().catch(() => null);
        if (!response.ok) {
            logger.error(`RAG service returned HTTP ${response.status}`);
            return res.status(502).json({
                error: "The travel assistant is temporarily unavailable. Please try again."
            });
        }

        return res.status(200).json(payload);
    } catch (error) {
        if (error.name === "AbortError") {
            logger.warn("RAG service request timed out.");
        } else {
            logger.error(`RAG service request failed: ${error.message}`);
        }
        return res.status(502).json({
            error: "The travel assistant is temporarily unavailable. Please try again."
        });
    } finally {
        clearTimeout(timeout);
    }
}

module.exports = { sendMessage };
