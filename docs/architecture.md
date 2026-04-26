# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Input Layer                             │
│   Job Description (PDF/TXT)        Resume (PDF/TXT)             │
└────────────────────┬───────────────────────┬────────────────────┘
                     │                       │
                     ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      InputParser                                │
│  parse_document() · validate_content() · _clean_text()          │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SkillExtractor                             │
│  extract_job_skills() · extract_resume_skills()                 │
│  _normalize_skill_names() · _categorize_skills()               │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
             RequiredSkills             ClaimedSkills
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AssessmentEngine                             │
│  generate_question() · evaluate_response() · assess_skill()    │
│  _adapt_difficulty() · _detect_evasion()                       │
│                                                                 │
│  ┌──────────────────────┐    ┌──────────────────────────────┐  │
│  │  ConversationState   │    │       GeminiClient           │  │
│  │  add_message()       │◄──►│  generate_text()             │  │
│  │  get_history()       │    │  generate_with_history()     │  │
│  │  reset_for_skill()   │    │  _call_with_retry()          │  │
│  └──────────────────────┘    └──────────────────────────────┘  │
└────────────────────────────────┬────────────────────────────────┘
                                 │ SkillAssessments
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                       GapAnalyzer                               │
│  analyze_gaps() · calculate_gap() · categorize_gap()           │
│  calculate_match_score() · rank_gaps_by_priority()             │
└────────────────────────────────┬────────────────────────────────┘
                                 │ GapAnalysis
                    ┌────────────┴────────────┐
                    ▼                         ▼
┌──────────────────────────┐   ┌──────────────────────────────────┐
│   LearningPlanGenerator  │   │       VisualizationEngine        │
│  generate_plan()         │   │  create_radar_chart()            │
│  sequence_learning_path()│   │  create_gap_bar_chart()          │
│  calculate_timeline()    │   └──────────────────────────────────┘
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│     ResourceCurator      │
│  curate_resources()      │
│  validate_url()          │
│  estimate_time()         │
└────────────┬─────────────┘
             │ LearningPlan
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      OutputGenerator                            │
│  generate_report() · export_json() · export_markdown()         │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
          assessment_report.json    assessment_report.md
```

## Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| `InputParser` | Parse PDF/text files, validate content, clean text |
| `SkillExtractor` | LLM-powered extraction of required and claimed skills |
| `GeminiClient` | Gemini API wrapper with retry logic and error handling |
| `ConversationState` | Multi-turn dialogue history management |
| `AssessmentEngine` | Conversational assessment, adaptive questioning, proficiency rating |
| `GapAnalyzer` | Pure-logic gap calculation, categorisation, match scoring |
| `LearningPlanGenerator` | Sequenced learning plan with adjacent-skill prioritisation |
| `ResourceCurator` | LLM-powered resource curation with URL validation |
| `VisualizationEngine` | Radar and bar charts via matplotlib |
| `OutputGenerator` | JSON and Markdown report generation |
| `MainController` | End-to-end orchestration and time budget management |

## Data Flow

```
JD + Resume → ParsedDocuments → RequiredSkills + ClaimedSkills
           → SkillAssessments → GapAnalysis → LearningPlan
           → Report (JSON + Markdown + Charts)
```

## Technology Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| LLM | Google Gemini 1.5 Flash | 1M tokens/day free tier |
| PDF Parsing | pdfplumber | Superior layout preservation |
| Visualisation | matplotlib | Native polar plots, no external services |
| Testing | pytest + Hypothesis | Property-based correctness verification |
| Language | Python 3.10+ | Type hints, dataclasses, modern stdlib |
