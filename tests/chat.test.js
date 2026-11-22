const { sendMessage } = require("../controllers/chat");

function createResponse() {
    return {
        statusCode: 200,
        body: null,
        status(code) {
            this.statusCode = code;
            return this;
        },
        json(body) {
            this.body = body;
            return this;
        }
    };
}

describe("RAG chat controller", () => {
    const originalFetch = global.fetch;

    afterEach(() => {
        global.fetch = originalFetch;
        delete process.env.RAG_SERVICE_URL;
        delete process.env.RAG_SERVICE_SECRET;
        delete process.env.RAG_CHAT_ENABLED;
    });

    test("rejects an empty message", async () => {
        const res = createResponse();
        await sendMessage({ body: { message: "  " } }, res);

        expect(res.statusCode).toBe(400);
        expect(res.body.error).toBe("Enter a message.");
    });

    test("forwards a valid message and history to Python", async () => {
        process.env.RAG_SERVICE_URL = "http://127.0.0.1:8000";
        process.env.RAG_SERVICE_SECRET = "test-secret";
        process.env.RAG_CHAT_ENABLED = "true";

        global.fetch = jest.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: jest.fn().mockResolvedValue({
                answer: "Room sharing is described in the guide.",
                sources: [{ documentId: "04-room-share", sourceFile: "04. room_share.pdf", pageNumber: 3 }],
                confidence: "high",
                grounded: true
            })
        });

        const res = createResponse();
        await sendMessage({
            body: {
                message: "How does room sharing work?",
                history: [{ role: "user", content: "I am traveling solo." }]
            },
            originalUrl: "/room-shares"
        }, res);

        expect(res.statusCode).toBe(200);
        expect(res.body.grounded).toBe(true);
        expect(global.fetch).toHaveBeenCalledTimes(1);

        const [url, options] = global.fetch.mock.calls[0];
        expect(url).toBe("http://127.0.0.1:8000/chat");
        expect(options.headers["X-RAG-Service-Key"]).toBe("test-secret");
        expect(JSON.parse(options.body).question).toBe("How does room sharing work?");
    });

    test("returns a controlled error when Python is unavailable", async () => {
        process.env.RAG_SERVICE_URL = "http://127.0.0.1:8000";
        process.env.RAG_SERVICE_SECRET = "test-secret";
        global.fetch = jest.fn().mockRejectedValue(new Error("ECONNREFUSED"));

        const res = createResponse();
        await sendMessage({ body: { message: "Where is the host dashboard?" } }, res);

        expect(res.statusCode).toBe(502);
        expect(res.body.error).toContain("temporarily");
    });
});
