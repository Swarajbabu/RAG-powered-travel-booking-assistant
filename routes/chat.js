const express = require("express");
const rateLimit = require("express-rate-limit");
const chatController = require("../controllers/chat.js");
const wrapAsync = require("../utility/wrapAsync");

const router = express.Router();

const chatLimiter = process.env.NODE_ENV === "test"
    ? (req, res, next) => next()
    : rateLimit({
        windowMs: 10 * 60 * 1000,
        limit: 20,
        standardHeaders: "draft-8",
        legacyHeaders: false,
        handler: (req, res) => res.status(429).json({
            error: "Too many chat requests. Please wait a few minutes."
        })
    });

router.post("/", chatLimiter, wrapAsync(chatController.sendMessage));

module.exports = router;
