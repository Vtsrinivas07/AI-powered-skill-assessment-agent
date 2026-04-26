"""
Streamlit Web Interface for the Skill Assessment Agent.

Provides a browser-based UI for uploading job descriptions and resumes,
running the conversational skill assessment, and viewing/downloading results.

Validates Requirements: 7.1, 7.5
"""

import io
import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

import streamlit as st

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent))

# ---------------------------------------------------------------------------
# Page configuration (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AI-Powered Skill Assessment Agent",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("app")


# ---------------------------------------------------------------------------
# Session-state helpers
# ---------------------------------------------------------------------------

def _init_state() -> None:
    """Initialise all session-state keys on first run."""
    defaults = {
        "assessment_result": None,   # dict returned by MainController.run_assessment()
        "running": False,            # True while assessment is in progress
        "error": None,               # Error message string or None
        "qa_pairs": [],              # List of (question, answer) tuples collected so far
        "current_question": None,    # Question waiting for user input
        "answer_submitted": False,   # Flag: user has submitted an answer
        "pending_answer": None,      # The answer text waiting to be consumed
        "phase": "upload",           # "upload" | "assess" | "results"
        "jd_path": None,             # Temp file path for job description
        "resume_path": None,         # Temp file path for resume
        "candidate_name": "",        # Optional candidate name
        "output_dir": "outputs",     # Output directory
        "interactive_mode": False,   # Whether to run interactive vs demo
        "required_skills": [],       # Skills to assess in interactive mode
        "current_skill_index": 0,    # Index of current skill being assessed
        "current_turn": 0,           # Turn counter for current skill
        "assessments": [],           # List of completed SkillAssessment objects
        "assessment_engine": None,   # AssessmentEngine instance
        "skill_extractor": None,     # SkillExtractor instance
        "gemini_client": None,       # GeminiClient instance
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

def _inject_css() -> None:
    st.markdown(
        """
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        
        <style>
        /* Global Styles */
        .stApp {
            background: radial-gradient(circle at top left, #1a1c2c, #0a0a0c);
            color: #e0e0e0;
            font-family: 'Inter', sans-serif;
        }
        
        h1, h2, h3, .main-header h1 {
            font-family: 'Outfit', sans-serif !important;
            font-weight: 700 !important;
            letter-spacing: -0.02em;
        }

        /* Glassmorphism Card */
        .glass-card {
            background: rgba(255, 255, 255, 0.03);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 20px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
            transition: transform 0.3s ease, border 0.3s ease;
        }
        .glass-card:hover {
            border: 1px solid rgba(255, 255, 255, 0.15);
        }

        /* Header Styling */
        .main-header {
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(168, 85, 247, 0.1) 100%);
            padding: 3rem 2rem;
            border-radius: 24px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            margin-bottom: 2.5rem;
            text-align: center;
        }
        .main-header h1 {
            background: linear-gradient(90deg, #818cf8, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 3.5rem !important;
            margin-bottom: 0.5rem;
        }
        .main-header p {
            color: #94a3b8;
            font-size: 1.2rem;
            max-width: 600px;
            margin: 0 auto;
        }

        /* Metric Cards */
        .metric-card {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.05);
            padding: 1.2rem;
            border-radius: 16px;
            margin-bottom: 1rem;
            transition: all 0.3s ease;
        }
        .metric-card:hover {
            background: rgba(255, 255, 255, 0.04);
            transform: translateY(-2px);
        }
        .gap-critical { border-left: 4px solid #ef4444 !important; }
        .gap-moderate { border-left: 4px solid #f59e0b !important; }
        .gap-minor    { border-left: 4px solid #10b981 !important; }
        .strength     { border-left: 4px solid #3b82f6 !important; }

        /* Sidebar Styling */
        section[data-testid="stSidebar"] {
            background: rgba(15, 17, 26, 0.8) !important;
            backdrop-filter: blur(20px);
            border-right: 1px solid rgba(255, 255, 255, 0.05);
        }
        
        /* Custom Button Styling */
        .stButton > button {
            border-radius: 12px !important;
            padding: 0.6rem 1.5rem !important;
            font-weight: 600 !important;
            transition: all 0.2s ease !important;
        }
        .stButton > button[kind="primary"] {
            background: linear-gradient(90deg, #6366f1, #a855f7) !important;
            border: none !important;
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3) !important;
        }
        .stButton > button[kind="primary"]:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 20px rgba(99, 102, 241, 0.4) !important;
        }

        /* Tab Styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            background-color: transparent;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: rgba(255, 255, 255, 0.03);
            border-radius: 12px 12px 0 0;
            padding: 0 20px;
            border: 1px solid rgba(255, 255, 255, 0.05);
            color: #94a3b8;
        }
        .stTabs [aria-selected="true"] {
            background-color: rgba(99, 102, 241, 0.1) !important;
            color: white !important;
            border-bottom: 2px solid #6366f1 !important;
        }

        /* Hide Streamlit default elements for cleaner look */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* Progress bar color */
        .stProgress > div > div > div > div {
            background: linear-gradient(90deg, #6366f1, #a855f7);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def _render_sidebar() -> None:
    with st.sidebar:
        # System config starts immediately


        st.markdown("---")

        # API key input
        st.markdown("### ⚙️ System Config")
        api_key = st.text_input(
            "Gemini API Key",
            type="password",
            value=os.getenv("GEMINI_API_KEY", ""),
            help="Your Google Gemini API key.",
        )
        if api_key:
            os.environ["GEMINI_API_KEY"] = api_key

        st.session_state.candidate_name = st.text_input(
            "Candidate Name",
            value=st.session_state.candidate_name,
            placeholder="e.g. Jane Smith",
        )

        st.session_state.output_dir = st.text_input(
            "Data Workspace",
            value=st.session_state.output_dir,
            help="Directory for persistence.",
        )

        st.markdown("---")
        # Navigation
        st.markdown("### 📍 Pipeline Status")
        phases = ["upload", "assess", "results"]
        labels = ["Step 1: Data Ingestion", "Step 2: Deep Analysis", "Step 3: Intelligence Report"]
        icons = ["📤", "🔍", "📊"]
        current = st.session_state.phase
        
        for phase, label, icon in zip(phases, labels, icons):
            if phase == current:
                st.markdown(
                    f"""
                    <div style="background: rgba(99, 102, 241, 0.1); padding: 0.8rem; border-radius: 12px; border-left: 4px solid #6366f1; color: white; font-weight: 600;">
                        {icon} {label}
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f"""
                    <div style="padding: 0.8rem; color: #64748b; opacity: 0.7;">
                        {icon} {label}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        st.markdown("---")
        st.markdown(
            """
            <div style="font-size: 0.75rem; color: #475569; text-align: center;">
                Powered by Gemini 2.5 Flash<br>
                v2.5 • Premium Edition
            </div>
            """,
            unsafe_allow_html=True
        )

        if st.button("🔄 Reset Environment", width="stretch"):
            _reset_state()
            st.rerun()


# ---------------------------------------------------------------------------
# Phase 1: Upload
# ---------------------------------------------------------------------------

def _render_upload_phase() -> None:
    st.markdown(
        """
        <div class="main-header">
            <h1>AI-Powered Skill Assessment & Personalised Learning Plan Agent</h1>
            <p>Conduct deep proficiency analysis and generate targeted growth pathways</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("📤 Document Upload")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Position Requirements**")
        jd_file = st.file_uploader(
            "Upload job description",
            type=["txt", "pdf"],
            key="jd_uploader",
            label_visibility="collapsed",
            help="Accepted formats: plain text (.txt) or PDF (.pdf)",
        )
        if jd_file:
            st.success(f"✅ {jd_file.name}")

    with col2:
        st.markdown("**Candidate Resume**")
        resume_file = st.file_uploader(
            "Upload resume",
            type=["txt", "pdf"],
            key="resume_uploader",
            label_visibility="collapsed",
            help="Accepted formats: plain text (.txt) or PDF (.pdf)",
        )
        if resume_file:
            st.success(f"✅ {resume_file.name}")
    st.markdown('</div>', unsafe_allow_html=True)

    # Validate and start
    is_mock = os.getenv("MOCK_LLM", "").lower() == "true"
    ready = jd_file is not None and resume_file is not None
    
    if not is_mock and not os.getenv("GEMINI_API_KEY"):
        st.warning("⚠️ Please enter your Gemini API key in the sidebar before starting.")
        ready = False

    st.markdown('<div style="margin-top: 2rem; text-align: center;">', unsafe_allow_html=True)
    if st.button(
        "🚀 Run Intelligence Assessment",
        disabled=not ready,
        width="stretch",
        type="primary",
        help="Starts the AI-powered technical interview"
    ):
        _save_uploads(jd_file, resume_file)
        st.session_state.interactive_mode = True # Default to full interactive interview
        st.session_state.phase = "assess"
        st.session_state.error = None
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


def _save_uploads(jd_file, resume_file) -> None:
    """Save uploaded files to temp paths and store in session state."""
    os.makedirs(st.session_state.output_dir, exist_ok=True)

    jd_suffix = Path(jd_file.name).suffix
    resume_suffix = Path(resume_file.name).suffix

    jd_tmp = tempfile.NamedTemporaryFile(
        delete=False, suffix=jd_suffix, dir=st.session_state.output_dir
    )
    jd_tmp.write(jd_file.getvalue())
    jd_tmp.close()
    st.session_state.jd_path = jd_tmp.name

    resume_tmp = tempfile.NamedTemporaryFile(
        delete=False, suffix=resume_suffix, dir=st.session_state.output_dir
    )
    resume_tmp.write(resume_file.getvalue())
    resume_tmp.close()
    st.session_state.resume_path = resume_tmp.name


# ---------------------------------------------------------------------------
# Phase 2: Assessment (non-interactive / demo)
# ---------------------------------------------------------------------------

def _render_assess_phase() -> None:
    st.header("🔍 Running Assessment")

    if st.session_state.interactive_mode:
        _render_interactive_assessment()
    else:
        _render_demo_assessment()


def _render_demo_assessment() -> None:
    """Run the full pipeline in demo mode (no user Q&A needed)."""
    if st.session_state.assessment_result is not None:
        # Already done — jump to results
        st.session_state.phase = "results"
        st.rerun()
        return

    if st.session_state.error:
        st.error(f"❌ {st.session_state.error}")
        if st.button("← Back to Upload"):
            st.session_state.phase = "upload"
            st.rerun()
        return

    progress_bar = st.progress(0, text="Initialising…")
    status_area = st.empty()

    steps = [
        (10, "📄 Parsing documents…"),
        (25, "🔍 Extracting skills…"),
        (45, "💬 Running assessment (demo mode)…"),
        (65, "📊 Analysing skill gaps…"),
        (80, "📚 Generating learning plan…"),
        (90, "📈 Creating visualisations…"),
        (98, "💾 Exporting reports…"),
    ]

    try:
        from main import MainController

        controller = MainController(
            output_dir=st.session_state.output_dir,
            max_assessment_time=900,
            max_turns_per_skill=3,
        )

        # Simulate step-by-step progress while running
        for pct, msg in steps[:-1]:
            progress_bar.progress(pct, text=msg)
            status_area.info(msg)
            time.sleep(0.3)

        result = controller.run_assessment(
            jd_path=st.session_state.jd_path,
            resume_path=st.session_state.resume_path,
            candidate_name=st.session_state.candidate_name or None,
            interactive=False,
        )

        progress_bar.progress(100, text="✅ Assessment complete!")
        status_area.success("Assessment complete!")
        st.session_state.assessment_result = result
        st.session_state.phase = "results"
        time.sleep(0.5)
        st.rerun()

    except Exception as exc:
        logger.exception("Assessment failed")
        st.session_state.error = str(exc)
        progress_bar.empty()
        status_area.error(f"❌ Assessment failed: {exc}")
        if st.button("← Back to Upload"):
            st.session_state.phase = "upload"
            st.rerun()


def _render_interactive_assessment() -> None:
    """Run a true interactive interview flow using Streamlit session state."""
    # 1. Initialize components if needed
    if not st.session_state.gemini_client:
        from src.gemini_client import GeminiClient
        from src.skill_extractor import SkillExtractor
        from src.assessment_engine import AssessmentEngine
        
        client = GeminiClient()
        st.session_state.gemini_client = client
        st.session_state.skill_extractor = SkillExtractor(client)
        st.session_state.assessment_engine = AssessmentEngine(client, max_turns=3)

    # 2. Extract skills if not yet done
    if not st.session_state.required_skills:
        with st.status("🛠️ Initializing assessment engine...", expanded=True) as status:
            st.write("Reading documents...")
            from src.input_parser import InputParser
            parser = InputParser()
            jd_content = parser.parse_document(st.session_state.jd_path).content
            resume_content = parser.parse_document(st.session_state.resume_path).content
            
            st.write("Identifying core skills from job description...")
            skills = st.session_state.skill_extractor.extract_job_skills(jd_content)
            st.session_state.required_skills = skills
            st.session_state.jd_content = jd_content
            st.session_state.resume_content = resume_content
            status.update(label="✅ Ready to interview!", state="complete")
        st.rerun()
        return

    # 3. Check if all skills are done
    if st.session_state.current_skill_index >= len(st.session_state.required_skills):
        _finalize_interactive_assessment()
        return

    current_skill = st.session_state.required_skills[st.session_state.current_skill_index]
    
    # Progress UI
    progress = st.session_state.current_skill_index / len(st.session_state.required_skills)
    st.progress(progress, text=f"Assessing Skill {st.session_state.current_skill_index + 1} of {len(st.session_state.required_skills)}: **{current_skill.name}**")

    # 4. Show Q&A history for CURRENT skill
    if st.session_state.qa_pairs:
        for q, a in st.session_state.qa_pairs:
            st.chat_message("assistant").write(q)
            st.chat_message("user").write(a)

    # 5. Generate or Show Question
    if not st.session_state.current_question:
        with st.spinner(f"AI is preparing a question about {current_skill.name}..."):
            question = st.session_state.assessment_engine.generate_question(
                current_skill, 
                current_skill.required_level, 
                st.session_state.current_turn
            )
            st.session_state.current_question = question
            st.rerun()

    st.chat_message("assistant").write(st.session_state.current_question)

    # 6. Get Answer
    answer = st.chat_input("Type your technical response here...")
    if answer:
        # Process answer
        with st.spinner("Evaluating your response..."):
            # Add to history
            st.session_state.qa_pairs.append((st.session_state.current_question, answer))
            
            # Evaluate
            rating_data = st.session_state.assessment_engine.evaluate_response(
                st.session_state.current_question,
                answer,
                current_skill
            )
            
            # Update engine state
            st.session_state.assessment_engine.conversation_state.add_message("assistant", st.session_state.current_question)
            st.session_state.assessment_engine.conversation_state.add_message("user", answer)
            
            # Update turn or skill
            st.session_state.current_turn += 1
            confidence = float(rating_data.get("confidence", 0.5))
            
            # Check for early exit or max turns
            if confidence >= 0.8 or st.session_state.current_turn >= 3:
                # Finalize this skill
                from src.models import SkillAssessment
                from datetime import datetime
                
                prof = st.session_state.assessment_engine._build_proficiency_rating(
                    rating_data, rating_data.get("evidence", [])
                )
                
                assessment = SkillAssessment(
                    skill=current_skill,
                    proficiency=prof,
                    questions_asked=[q for q, a in st.session_state.qa_pairs],
                    responses=[a for q, a in st.session_state.qa_pairs],
                    duration_seconds=0, 
                    timestamp=datetime.now()
                )
                st.session_state.assessments.append(assessment)
                
                # Reset for next skill
                st.session_state.current_skill_index += 1
                st.session_state.current_turn = 0
                st.session_state.qa_pairs = []
                st.session_state.assessment_engine.conversation_state.reset_for_skill("")
            
            st.session_state.current_question = None
            st.rerun()

def _finalize_interactive_assessment() -> None:
    """Complete the report generation after interactive Q&A."""
    with st.status("📊 Compiling final intelligence report...", expanded=True) as status:
        from src.gap_analyzer import GapAnalyzer
        from src.resource_curator import ResourceCurator
        from src.learning_plan import LearningPlanGenerator
        from src.visualization import VisualizationEngine
        from src.output_generator import OutputGenerator
        
        st.write("Analyzing skill gaps...")
        analyzer = GapAnalyzer()
        gap_analysis = analyzer.analyze_gaps(st.session_state.required_skills, st.session_state.assessments)
        
        st.write("Curating personalized learning resources...")
        curator = ResourceCurator(st.session_state.gemini_client)
        planner = LearningPlanGenerator(resource_curator=curator)
        learning_plan = planner.generate_plan(gap_analysis, st.session_state.assessments)
        
        st.write("Generating visualizations...")
        viz_engine = VisualizationEngine(output_dir=st.session_state.output_dir)
        visualizations = []
        try:
            visualizations.append(viz_engine.create_radar_chart(gap_analysis))
            visualizations.append(viz_engine.create_gap_bar_chart(gap_analysis))
        except:
            pass
            
        st.write("Exporting final report...")
        generator = OutputGenerator(output_dir=st.session_state.output_dir)
        from main import MainController
        job_title = MainController._infer_job_title(st.session_state.jd_content)
        
        report = generator.generate_report(
            assessments=st.session_state.assessments,
            gap_analysis=gap_analysis,
            learning_plan=learning_plan,
            visualizations=visualizations,
            job_title=job_title,
            candidate_name=st.session_state.candidate_name or None
        )
        
        json_path = generator.export_json(report)
        md_path = generator.export_markdown(report)
        
        st.session_state.assessment_result = {
            "report": report,
            "json_path": json_path,
            "markdown_path": md_path,
            "visualizations": visualizations
        }
        status.update(label="✅ Analysis complete!", state="complete")
        
    st.session_state.phase = "results"
    time.sleep(1)
    st.rerun()


# ---------------------------------------------------------------------------
# Phase 3: Results
# ---------------------------------------------------------------------------

def _render_results_phase() -> None:
    result = st.session_state.assessment_result
    if result is None:
        st.warning("No results available. Please run an assessment first.")
        if st.button("← Back to Upload"):
            st.session_state.phase = "upload"
            st.rerun()
        return

    report = result["report"]
    gap_analysis = report.gap_analysis
    learning_plan = report.learning_plan

    # ----------------------------------------------------------------
    # Header
    # ----------------------------------------------------------------
    st.markdown(
        f"""
        <div class="main-header" style="padding: 2rem 1rem;">
            <h1 style="font-size: 2.5rem !important;">Assessment Intelligence</h1>
            <p><strong>{report.job_title}</strong> &nbsp;•&nbsp; {report.assessment_date.strftime('%Y-%m-%d')}{" &nbsp;•&nbsp; " + report.candidate_name if report.candidate_name else ""}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ----------------------------------------------------------------
    # Summary metrics
    # ----------------------------------------------------------------
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Match Score", f"{gap_analysis.match_score:.1f}/100")
    with col2:
        st.metric("Skills Assessed", len(report.assessments))
    with col3:
        st.metric("Critical Gaps", len(gap_analysis.critical_gaps))
    with col4:
        st.metric("Learning Hours", learning_plan.total_hours)

    st.markdown(
        f"""
        <div style="margin-top: 1.5rem; color: #94a3b8; font-style: italic; text-align: center;">
            "{report.summary}"
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # ----------------------------------------------------------------
    # Tabs
    # ----------------------------------------------------------------
    tab_gaps, tab_assessments, tab_plan, tab_charts, tab_download = st.tabs([
        "🔍 Gap Analysis",
        "📝 Skill Assessments",
        "📚 Learning Plan",
        "📈 Charts",
        "⬇️ Download Reports",
    ])

    with tab_gaps:
        _render_gap_analysis(gap_analysis)

    with tab_assessments:
        _render_assessments(report.assessments)

    with tab_plan:
        _render_learning_plan(learning_plan)

    with tab_charts:
        _render_charts(result.get("visualizations", []))

    with tab_download:
        _render_downloads(result)


def _render_gap_analysis(gap_analysis) -> None:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("Skill Gap Analysis")

    # Match score gauge
    score = gap_analysis.match_score
    colour = "#10b981" if score >= 70 else "#f59e0b" if score >= 40 else "#ef4444"
    st.markdown(
        f"""
        <div style="text-align:center; padding: 2rem 1rem; margin-bottom: 2rem; background: rgba(255,255,255,0.02); border-radius: 24px;">
            <div style="font-size: 4rem; font-weight: 800; color: {colour}; font-family: 'Outfit', sans-serif;">
                {score:.1f}<span style="font-size:1.5rem; opacity: 0.6;">/100</span>
            </div>
            <div style="font-size: 1.1rem; color: #94a3b8; letter-spacing: 0.05em; text-transform: uppercase;">Overall Match Score</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        if gap_analysis.strengths:
            st.markdown("### ✅ Strengths")
            for s in gap_analysis.strengths:
                st.markdown(
                    f'<div class="metric-card strength">💪 {s}</div>',
                    unsafe_allow_html=True,
                )

        if gap_analysis.critical_gaps:
            st.markdown("### 🔴 Critical Gaps")
            for g in gap_analysis.critical_gaps:
                st.markdown(
                    f'<div class="metric-card gap-critical">'
                    f'<strong>{g.skill}</strong><br>'
                    f'<small style="color: #94a3b8;">{g.assessed_level.name} → {g.required_level.name} '
                    f'(gap: {g.gap_magnitude})</small>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    with col2:
        if gap_analysis.moderate_gaps:
            st.markdown("### 🟠 Moderate Gaps")
            for g in gap_analysis.moderate_gaps:
                st.markdown(
                    f'<div class="metric-card gap-moderate">'
                    f'<strong>{g.skill}</strong><br>'
                    f'<small style="color: #94a3b8;">{g.assessed_level.name} → {g.required_level.name} '
                    f'(gap: {g.gap_magnitude})</small>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        if gap_analysis.minor_gaps:
            st.markdown("### 🟡 Minor Gaps")
            for g in gap_analysis.minor_gaps:
                st.markdown(
                    f'<div class="metric-card gap-minor">'
                    f'<strong>{g.skill}</strong><br>'
                    f'<small style="color: #94a3b8;">{g.assessed_level.name} → {g.required_level.name} '
                    f'(gap: {g.gap_magnitude})</small>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
    st.markdown('</div>', unsafe_allow_html=True)


def _render_assessments(assessments) -> None:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("Individual Skill Assessments")

    if not assessments:
        st.info("No assessments available.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    for a in assessments:
        gap = a.skill.required_level.value - a.proficiency.level.value
        if gap <= 0:
            icon = "✅"
            border_color = "#10b981"
        elif gap >= 2:
            icon = "🔴"
            border_color = "#ef4444"
        else:
            icon = "🟠"
            border_color = "#f59e0b"

        with st.expander(f"{icon} {a.skill.name} — {a.proficiency.level.name}", expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Required", a.skill.required_level.name)
            with col2:
                st.metric("Assessed", a.proficiency.level.name)
            with col3:
                st.metric("Confidence", f"{a.proficiency.confidence:.0%}")

            st.markdown(f"**Justification:** {a.proficiency.justification}")

            if a.proficiency.evidence:
                st.markdown("**Evidence identified:**")
                for ev in a.proficiency.evidence:
                    st.markdown(f"- {ev}")

            if a.questions_asked:
                st.markdown("**Verification questions:**")
                for q in a.questions_asked:
                    st.markdown(f"- <i style='color: #94a3b8;'>{q}</i>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def _render_learning_plan(learning_plan) -> None:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("Personalised Growth Roadmap")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Hours", learning_plan.total_hours)
    with col2:
        st.metric("Timeline", f"{learning_plan.timeline_weeks} weeks")
    with col3:
        st.metric("Steps", len(learning_plan.steps))

    if learning_plan.prerequisites_needed:
        st.markdown(
            f"""
            <div style="background: rgba(245, 158, 11, 0.1); padding: 1rem; border-radius: 12px; border-left: 4px solid #f59e0b; margin-bottom: 1.5rem;">
                <strong>⚠️ Foundational Requirements:</strong> {", ".join(learning_plan.prerequisites_needed)}
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("---")

    for i, step in enumerate(learning_plan.steps, 1):
        adj_badge = " <span style='background: rgba(59, 130, 246, 0.2); color: #3b82f6; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; vertical-align: middle; margin-left: 8px;'>ADJACENT</span>" if (
            step.current_level.value + 1 == step.target_level.value
        ) else ""

        with st.expander(
            f"Phase {i}: {step.skill} — {step.estimated_hours}h",
            expanded=(i == 1),
        ):
            st.markdown(f"**Path:** {step.current_level.name} ➡️ {step.target_level.name} {adj_badge}", unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Goal:** {step.milestone_criteria}")
            with col2:
                if step.prerequisites:
                    st.markdown("**Prerequisites:** " + ", ".join(step.prerequisites))

            st.markdown("**Curated Resources:**")
            for r in step.resources:
                free_tag = "🆓" if r.is_free else "💰"
                st.markdown(
                    f'<div class="resource-item" style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); padding: 1rem; border-radius: 12px; margin-bottom: 0.5rem;">'
                    f'<div style="display: flex; justify-content: space-between; align-items: flex-start;">'
                    f'<span>{free_tag} <a href="{r.url}" target="_blank" style="color: #6366f1; text-decoration: none; font-weight: 600;">{r.title}</a></span>'
                    f'<span style="font-size: 0.8rem; background: rgba(255,255,255,0.05); padding: 2px 6px; border-radius: 4px;">{r.difficulty}</span>'
                    f'</div>'
                    f'<div style="font-size: 0.85rem; color: #94a3b8; margin-top: 4px;">'
                    f'{r.provider} • {r.format.value} • ~{r.estimated_hours}h'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    if learning_plan.milestones:
        st.markdown("<h3 style='margin-top: 2rem;'>🏁 Growth Milestones</h3>", unsafe_allow_html=True)
        for m in learning_plan.milestones:
            st.markdown(f"- {m}")
    st.markdown('</div>', unsafe_allow_html=True)


def _render_charts(visualization_paths) -> None:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("Visual Intelligence")

    if not visualization_paths:
        st.info("No visual data available.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    for path in visualization_paths:
        if os.path.exists(path):
            st.image(path, width="stretch")
            st.markdown("<br>", unsafe_allow_html=True)
        else:
            st.warning(f"Visualization missing: {path}")
    st.markdown('</div>', unsafe_allow_html=True)


def _render_downloads(result: dict) -> None:
    st.subheader("Download Reports")

    col1, col2 = st.columns(2)

    with col1:
        json_path = result.get("json_path")
        if json_path and os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                json_content = f.read()
            st.download_button(
                label="⬇️ Download JSON Report",
                data=json_content,
                file_name="assessment_report.json",
                mime="application/json",
                width="stretch",
            )
            st.caption(f"File: {json_path}")
        else:
            st.info("JSON report not available.")

    with col2:
        md_path = result.get("markdown_path")
        if md_path and os.path.exists(md_path):
            with open(md_path, "r", encoding="utf-8") as f:
                md_content = f.read()
            st.download_button(
                label="⬇️ Download Markdown Report",
                data=md_content,
                file_name="assessment_report.md",
                mime="text/markdown",
                width="stretch",
            )
            st.caption(f"File: {md_path}")
        else:
            st.info("Markdown report not available.")

    # Chart downloads
    viz_paths = result.get("visualizations", [])
    if viz_paths:
        st.divider()
        st.markdown("**Download Charts:**")
        chart_cols = st.columns(len(viz_paths))
        for col, path in zip(chart_cols, viz_paths):
            if os.path.exists(path):
                with open(path, "rb") as f:
                    img_bytes = f.read()
                fname = os.path.basename(path)
                with col:
                    st.download_button(
                        label=f"⬇️ {fname}",
                        data=img_bytes,
                        file_name=fname,
                        mime="image/png",
                        width="stretch",
                    )

    st.divider()
    st.markdown("**Preview Markdown Report:**")
    if md_path and os.path.exists(md_path):
        with open(md_path, "r", encoding="utf-8") as f:
            md_preview = f.read()
        with st.expander("📄 Markdown Report Preview", expanded=False):
            st.markdown(md_preview)


# ---------------------------------------------------------------------------
# State reset
# ---------------------------------------------------------------------------

def _reset_state() -> None:
    """Clear all session state to start fresh."""
    keys_to_clear = [
        "assessment_result", "running", "error", "qa_pairs",
        "current_question", "answer_submitted", "pending_answer",
        "phase", "jd_path", "resume_path",
    ]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point for the Streamlit application."""
    # Load .env if available
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    _init_state()
    _inject_css()
    _render_sidebar()

    phase = st.session_state.phase

    if phase == "upload":
        _render_upload_phase()
    elif phase == "assess":
        _render_assess_phase()
    elif phase == "results":
        _render_results_phase()
    else:
        st.error(f"Unknown phase: {phase}")
        _reset_state()
        st.rerun()


if __name__ == "__main__":
    main()
