# 🧠 Autonomous Multi-Agent Research & Fact-Checking Engine

An enterprise-grade autonomous research and intelligence synthesis system powered by **LangChain**, **LangGraph**, **LangSmith**, and **OpenRouter**.

The engine orchestrates specialized autonomous agents (Planner, Web Researcher, Fact-Checker/Critic, and Executive Writer) inside a stateful, cyclical graph with automated self-correction, Docker containerization, and a convenient Makefile.

---

## 🌐 OpenRouter: Best Free Models (Indonesian & English)

This project is pre-configured to use **OpenRouter** free tier. The top recommended models for both Bahasa Indonesia and English are:

1. **google/gemini-2.0-flash-exp:free** (Recommended) - Lightning fast, outstanding bilingual fluency in Indonesian and English, strong structured output support.
2. **qwen/qwen-2.5-72b-instruct:free** - Premier open multilingual model with nuanced Southeast Asian / Indonesian vocabulary.
3. **meta-llama/llama-3.3-70b-instruct:free** - 70B parameter model with deep reasoning and strong bilingual synthesis.
4. **deepseek/deepseek-r1:free** - Chain-of-thought reasoning powerhouse for complex technical topics.

---

## 🛠️ Makefile Command Reference

A Makefile is provided to streamline all development, execution, and Docker workflows:

| Command | Description |
| :--- | :--- |
| make env | Copies .env.example to .env |
| make setup | Creates local Python virtual environment & installs dependencies |
| make run | Runs the interactive CLI research agent locally |
| make eval | Runs the LangSmith automated benchmark evaluation suite |
| make docker-build | Builds the Docker image (multi-agent-researcher:latest) |
| make docker-run | Runs the research agent inside an isolated Docker container |
| make docker-up | Runs the container using Docker Compose with volume mount |
| make clean | Cleans temporary cache and generated artifacts |

---

## 🚀 Quickstart Guide

### Option A: Running with Docker (Recommended)

1. Create your .env file and set your OPENROUTER_API_KEY:
   `ash
   make env
   `
2. Build and run using Docker Compose:
   `ash
   make docker-up
   `

### Option B: Running Locally

1. Setup virtual environment:
   `ash
   make setup
   `
2. Run the agent:
   `ash
   make run
   `

---

## 📊 Automated Evaluation Suite (LangSmith)

To benchmark the agent's research depth and fact-checking reliability across a test dataset:

`ash
make eval
`
