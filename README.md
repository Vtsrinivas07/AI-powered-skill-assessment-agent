# Skill Assessment Agent

An AI-powered agent that takes a Job Description and a candidate's resume, conversationally assesses real proficiency on each required skill, identifies gaps, and generates a personalised learning plan with curated resources and time estimates.

Built for the **Catalyst Hackathon** by deccan.ai.

---

## Features

- 📄 **PDF & text input** — accepts job descriptions and resumes in `.pdf` or `.txt` format
- 🤖 **Conversational assessment** — multi-turn dialogue probes real skill depth, not just resume claims
- 📊 **Gap analysis** — categorises gaps as critical / moderate / minor with an overall match score
- 📈 **Visual reports** — radar chart and bar chart comparing required vs. assessed proficiency
- 🎯 **Adjacent-skill focus** — learning plan prioritises skills the candidate can realistically acquire
- 📚 **Curated resources** — free learning materials with time estimates per skill
- 📝 **Dual export** — structured JSON and human-readable Markdown reports

---

## Quick Start

### Prerequisites

- Python 3.10+
- A free [Google Gemini API key](https://makersuite.google.com/app/apikey)

### Installation

```bash
git clone <your-repo-url>
cd skill-assessment-agent

python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env and set GEMINI_API_KEY=your_key_here

### Mock Mode (For Demos)

If you don't have a Gemini API key or want to run a quick demo without hitting rate limits, you can enable **Mock Mode**:

1. Open your `.env` file.
2. Set `MOCK_LLM=true`.

When active, the agent uses predefined responses to simulate the full assessment workflow.
```

### Run (CLI)

```bash
# Interactive mode (you answer the assessment questions)
python main.py --jd samples/job_description.txt --resume samples/resume.txt

# Demo mode (placeholder responses, no user input needed)
python main.py --jd samples/job_description.txt --resume samples/resume.txt --no-interactive

# PDF inputs
python main.py --jd job.pdf --resume cv.pdf --output-dir my_reports
```

### Run (Web UI)

```bash
streamlit run app.py
```

Then open [http://localhost:8501](http://localhost:8501) in your browser.

The web interface guides you through three steps:
1. **Upload** — drag-and-drop your job description and resume (PDF or text)
2. **Assessment** — the agent evaluates skills via the Gemini API
3. **Results** — view the match score, gap analysis, learning plan, charts, and download reports

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--jd` | required | Job description file (PDF or text) |
| `--resume` | required | Resume file (PDF or text) |
| `--output-dir` | `outputs` | Directory for reports and charts |
| `--max-assessment-time` | `900` | Max total assessment time (seconds) |
| `--max-turns` | `3` | Max question-answer turns per skill |
| `--candidate-name` | — | Candidate name for the report |
| `--no-interactive` | — | Demo mode with placeholder responses |

---

## Output

Reports are saved to `outputs/` (or your `--output-dir`):

| File | Description |
|------|-------------|
| `assessment_report.json` | Structured data — all assessments, gaps, learning plan |
| `assessment_report.md` | Human-readable report with embedded chart references |
| `radar_chart.png` | Radar chart: required vs. assessed proficiency |
| `gap_bar_chart.png` | Bar chart: gap magnitude per skill |

---

## Architecture

```
InputParser → SkillExtractor → AssessmentEngine → GapAnalyzer
                                     ↕                  ↓
                              ConversationState   LearningPlanGenerator
                              GeminiClient              ↓
                                               ResourceCurator
                                                       ↓
                                              VisualizationEngine
                                                       ↓
                                              OutputGenerator → JSON + Markdown
```

See [`docs/architecture.md`](docs/architecture.md) for the full diagram and component descriptions.

---

## Project Structure

```
skill-assessment-agent/
├── main.py                    # CLI entry point + MainController
├── app.py                     # Streamlit web interface
├── config.py                  # Environment variable management
├── requirements.txt           # Dependencies
├── .env.example               # Environment template
├── src/
│   ├── models.py              # Data models (enums + dataclasses)
│   ├── exceptions.py          # Custom exceptions
│   ├── input_parser.py        # PDF/text parsing
│   ├── gemini_client.py       # Gemini API wrapper
│   ├── skill_extractor.py     # LLM-powered skill extraction
│   ├── conversation_state.py  # Multi-turn dialogue state
│   ├── assessment_engine.py   # Conversational assessment
│   ├── gap_analyzer.py        # Gap calculation and scoring
│   ├── learning_plan.py       # Learning plan generation
│   ├── resource_curator.py    # Resource curation
│   ├── visualization.py       # Chart generation
│   └── output_generator.py    # Report export
├── tests/
│   ├── test_config.py
│   └── test_input_parser.py
├── samples/
│   ├── job_description.txt    # Sample JD (Senior Backend Engineer)
│   └── resume.txt             # Sample resume
└── docs/
    ├── architecture.md
    └── methodology.md
```

---

## Testing

```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Unit tests only
pytest tests/ -k "not integration"
```

---

## APIs & Tools Used

| Tool | Purpose | Tier |
|------|---------|------|
| Google Gemini 1.5 Flash | LLM for skill extraction, assessment, resource curation | Free (1M tokens/day) |
| pdfplumber | PDF text extraction | Free / open-source |
| matplotlib | Chart generation | Free / open-source |
| Hypothesis | Property-based testing | Free / open-source |
| pytest | Test runner | Free / open-source |
| python-dotenv | Environment variable loading | Free / open-source |

---

## Scoring Logic

See [`docs/methodology.md`](docs/methodology.md) for:
- Proficiency level definitions (NONE → EXPERT)
- Gap categorisation rules (critical / moderate / minor)
- Match score formula
- Adjacent-skill definition and prioritisation
- Learning time estimates

---

## Repository Access

Please grant access to **hackathon@deccan.ai** before submitting:

```bash
# GitHub: Settings → Collaborators → Add hackathon@deccan.ai
```

---

## License

MIT
