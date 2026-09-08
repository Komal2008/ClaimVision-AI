import csv
# -*- coding: utf-8 -*-
import io
import json
import os
import textwrap
import time
import hmac
from datetime import datetime
from html import escape
from pathlib import Path

import base64
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

from report_generator import generate_pdf_report
from src.image_analyzer import analyze_image

import yaml
from dotenv import load_dotenv

load_dotenv()

try:
    import streamlit_authenticator as stauth
except ImportError:
    stauth = None


APP_TITLE = "ClaimVision AI"
APP_SUBTITLE = "AI-Powered Damage Claim Verification"
REPO_ROOT = Path(__file__).resolve().parents[1]
LOGO_PATH = REPO_ROOT / "assets" / "logo.png"
TEMP_IMAGE_PATH = Path("temp.jpg")
OUTPUT_CSV_PATH = REPO_ROOT / "dataset" / "output.csv"
MAX_FILE_SIZE = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
AUTH_CONFIG_PATH = Path(__file__).parent / "auth.yaml"


def ensure_auth_config():
    if not AUTH_CONFIG_PATH.exists():
        os.makedirs(AUTH_CONFIG_PATH.parent, exist_ok=True)
        cookie_key = os.getenv("CLAIMVISION_AUTH_KEY", "claimvision_secret_key_change_me_in_production")
        default = {
            "credentials": {
                "usernames": {
                    "admin": {
                        "email": "admin@claimvision.ai",
                        "name": "Admin",
                        "password": "admin123",
                    }
                }
            },
            "cookie": {
                "name": "claimvision_auth",
                "key": cookie_key,
                "expiry_days": 30,
            },
        }
        with open(AUTH_CONFIG_PATH, "w") as f:
            yaml.dump(default, f, default_flow_style=False)
    return AUTH_CONFIG_PATH


def load_auth_config():
    ensure_auth_config()
    with open(AUTH_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def save_auth_config(config):
    with open(AUTH_CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def clear_authentication():
    st.session_state["authenticated"] = False
    st.session_state["auth_name"] = ""
    st.session_state["auth_username"] = ""
    st.session_state["authentication_status"] = None
    st.session_state.pop("chat_messages", None)


def render_login_page():
    """Render the only unauthenticated view."""
    st.markdown(
        """
        <style>
        .login-shell { max-width: 1180px; margin: 4vh auto; }
        .login-shell > div[data-testid="stHorizontalBlock"] {
            align-items: stretch; gap: 3.5rem;
        }
        .login-shell > div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
            flex: 1 1 0; width: 50%; max-width: 50%; min-width: 0;
        }
        .login-brand, .login-shell > div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:has([data-testid="stTextInput"]) {
            min-height: 600px; height: 100%; box-sizing: border-box;
            border: 1px solid rgba(148,163,184,.2);
            background: rgba(15,23,42,.82);
            box-shadow: 0 24px 70px rgba(0,0,0,.3);
            border-radius: 24px; padding: 2.5rem;
        }
        .login-brand { display:flex; flex-direction:column; justify-content:flex-start; background:
            radial-gradient(circle at 80% 20%, rgba(99,102,241,.25), transparent 35%),
            rgba(15,23,42,.55); }
        .login-headline-row { display:flex; align-items:flex-start; margin-top:1.1rem; }
        .login-headline-row h1 { margin-top:0; }
        .login-brand h1 { color:#f8fafc; font-size:clamp(2.5rem,5vw,4.5rem); line-height:1.05; }
        .login-brand h1 span { color:#60a5fa; }
        .login-brand p, .login-card p { color:#94a3b8; line-height:1.6; }
        .login-feature { color:#dbeafe; margin:.9rem 0; font-weight:700; }
        .login-eyebrow { color:#60a5fa; font-size:.72rem; font-weight:800; letter-spacing:.12em; }
        .login-shell > div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:has([data-testid="stTextInput"]) {
            background:
                linear-gradient(145deg, rgba(56,189,248,.08), transparent 42%),
                rgba(15,23,42,.9);
        }
        .login-brand-logo {
            display: block; width: 60px; height: 60px; object-fit: cover;
            margin: .35rem 1.35rem 0 0; border-radius: 15px; flex: 0 0 auto;
            border: 1px solid rgba(56,189,248,.35);
            box-shadow: 0 0 30px rgba(56,189,248,.2);
        }
        .login-card-heading h2 { color:#f8fafc; margin:.35rem 0; }
        .login-card-heading p { margin-bottom:1.35rem; }
        .login-shell [data-testid="stForm"] { border:0; padding:0; background:transparent; }
        .login-shell [data-testid="stTextInput"] { margin-top:.35rem; }
        .login-shell [data-testid="stCheckbox"] { margin-top:.25rem; }
        .login-shell [data-testid="stButton"] button {
            min-height: 2.9rem; border-radius: 11px;
            transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
        }
        .login-shell [data-testid="stButton"] button:hover {
            transform: translateY(-1px); box-shadow: 0 12px 28px rgba(56,189,248,.15);
            border-color: rgba(96,165,250,.65);
        }
        .login-google [data-testid="stButton"] button {
            color: #202124; background: #fff; border-color: #d9dce1;
            font-weight: 700;
        }
        .login-google [data-testid="stButton"] button::before {
            content: "G"; display: inline-block; margin-right: .55rem;
            font-size: 1.08rem; font-weight: 900;
            background: conic-gradient(from 35deg, #4285f4 0 25%, #34a853 25% 48%, #fbbc05 48% 68%, #ea4335 68% 84%, #4285f4 84%);
            -webkit-background-clip: text; background-clip: text; color: transparent;
        }
        .login-google [data-testid="stButton"] button:hover {
            background: #f8f9fa; border-color: #b8c0cc;
            box-shadow: 0 8px 18px rgba(15,23,42,.16);
        }
        .login-links {
            display: flex; align-items: center; justify-content: center;
            gap: .75rem; margin-top: .55rem; color: #64748b;
        }
        .login-links [data-testid="stButton"] button {
            min-height: auto; padding: .2rem .1rem; border: 0;
            background: transparent; color: #67b7ff; box-shadow: none;
            font-size: .82rem; font-weight: 700;
        }
        .login-links [data-testid="stButton"] button:hover {
            transform: none; border: 0; background: transparent;
            color: #b9e5ff; box-shadow: none;
        }
        .login-link-separator { color: #475569; font-size: .85rem; }
        @media (max-width: 900px) {
            .login-shell { margin: 1rem auto; }
            .login-shell > div[data-testid="stHorizontalBlock"] { gap: 1rem; }
            .login-shell > div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
                width: 100%; max-width: 100%;
            }
            .login-brand, .login-shell > div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:has([data-testid="stTextInput"]) {
                min-height: auto; padding: 1.5rem;
            }
            .login-brand h1 { font-size: clamp(2.3rem, 9vw, 3.8rem); }
            .login-headline-row { align-items:flex-start; }
            .login-headline-row .login-brand-logo { width:50px; height:50px; margin-right:.8rem; }
                .login-links { gap: .35rem; }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="login-shell">', unsafe_allow_html=True)
    brand_col, card_col = st.columns([1, 1], gap="large")
    with brand_col:
        logo_data_uri = get_logo_data_uri()
        logo_markup = (
            f'<img class="login-brand-logo" src="{logo_data_uri}" alt="ClaimVision AI logo" />'
            if logo_data_uri
            else ""
        )
        st.markdown(
            f"""
            <section class="login-brand">
                <div class="login-headline-row">
                    {logo_markup}
                    <h1>Intelligent Claims.<br><span>Faster Decisions.</span></h1>
                </div>
                <p>Transform insurance claim verification with AI-powered image analysis,
                intelligent document processing, and faster claim decisions.</p>
                <div class="login-feature">✓ AI-Powered Claim Analysis</div>
                <div class="login-feature">✓ Damage Detection &amp; Verification</div>
                <div class="login-feature">✓ Faster Insurance Decisions</div>
            </section>
            """,
            unsafe_allow_html=True,
        )
    with card_col:
        st.markdown(
            '<div class="login-card-heading"><div class="login-eyebrow">SECURE WORKSPACE</div>'
            '<h2>Welcome back</h2><p>Sign in to your ClaimVision AI account</p></div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="login-google">', unsafe_allow_html=True)
        if st.button("Continue with Google", key="google_login", use_container_width=True):
            st.info("Google sign-in is not configured yet. Please use email/password.")
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("**OR CONTINUE WITH EMAIL**")
        with st.form("premium_login", clear_on_submit=False):
            username = st.text_input(
                "Username", placeholder="komal"
            )
            password = st.text_input(
                "Password", type="password", placeholder="komal123"
            )
            remember_me = st.checkbox("Remember me", value=True)
            submitted = st.form_submit_button("Sign In  →", use_container_width=True)
        st.markdown('<div class="login-links">', unsafe_allow_html=True)
        link_left, link_separator, link_right = st.columns([1, 0.12, 1], gap="small")
        with link_left:
            if st.button("Forgot password?", key="forgot_password", use_container_width=True):
                st.info("Password recovery is not configured yet. Please contact your administrator.")
        with link_separator:
            st.markdown('<div class="login-link-separator">|</div>', unsafe_allow_html=True)
        with link_right:
            if st.button("Create an account", key="create_account", use_container_width=True):
                st.info("Account registration is not configured yet.")
        st.markdown("</div>", unsafe_allow_html=True)
        if submitted:
            if not username.strip():
                st.error("Please enter your username.")
                return
            if not password:
                st.error("Please enter your password.")
                return
            with st.spinner("Authenticating..."):
                # Temporary local demo credentials; replace with production auth later.
                valid_demo = hmac.compare_digest(username.strip().lower(), "komal") and hmac.compare_digest(
                    password, "komal123"
                )
                if not valid_demo:
                    st.error("Invalid email or password. Please try again.")
                    return
            st.session_state["authenticated"] = True
            st.session_state["auth_name"] = username
            st.session_state["auth_username"] = username
            st.session_state["authentication_status"] = True
            st.session_state["remember_me"] = remember_me
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def validate_uploaded_file(uploaded_file):
    errors = []
    if uploaded_file is None:
        errors.append("No file was uploaded.")
        return errors

    ext = Path(uploaded_file.name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        errors.append(f"Unsupported file type '{ext}'. Only JPG, JPEG, and PNG images are allowed.")

    file_size = len(uploaded_file.getbuffer())
    if file_size == 0:
        errors.append("The uploaded file is empty.")
    elif file_size > MAX_FILE_SIZE:
        errors.append(f"File size exceeds {MAX_FILE_SIZE // (1024 * 1024)} MB.")

    return errors


def get_logo_image():
    if LOGO_PATH.exists():
        try:
            with Image.open(LOGO_PATH) as image:
                return image.copy()
        except OSError:
            return None
    return None


def get_logo_data_uri():
    if not LOGO_PATH.exists():
        return ""
    encoded = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def configure_page():
    st.set_page_config(
        page_title="ClaimVision AI | Evidence Review",
        page_icon=get_logo_image(),
        layout="wide",
        initial_sidebar_state="expanded",
    )


def inject_css():
    st.markdown(
        """
        <style>
            :root {
                --bg: #080d17;
                --panel: #101827;
                --panel-soft: #121c2e;
                --panel-border: rgba(148, 163, 184, 0.18);
                --text: #e5eefb;
                --muted: #91a1b7;
                --accent: #38bdf8;
                --accent-strong: #22c55e;
                --warning: #f59e0b;
                --danger: #f43f5e;
                --shadow: 0 20px 50px rgba(0, 0, 0, 0.35);
            }

            .stApp {
                background:
                    radial-gradient(circle at top left, rgba(56, 189, 248, 0.16), transparent 30rem),
                    linear-gradient(135deg, #080d17 0%, #0b1220 45%, #101827 100%);
                color: var(--text);
            }

            [data-testid="stSidebar"] {
                background: #07111f;
                border-right: 1px solid var(--panel-border);
            }

            [data-testid="stSidebar"] > div:first-child {
                padding-top: 1rem;
            }

            [data-testid="stSidebar"] * {
                color: var(--text);
            }

            [data-testid="stLogo"] {
                padding: 0.35rem 0.6rem 0.1rem;
            }

            [data-testid="stLogo"] img {
                border-radius: 13px;
                box-shadow: 0 0 24px rgba(56, 189, 248, 0.18);
            }

            .sidebar-brand {
                display: flex;
                align-items: center;
                gap: 0.85rem;
                width: 100%;
                padding: 0.75rem 0.15rem 1.05rem;
                margin-bottom: 0.35rem;
            }

            .sidebar-brand-logo {
                width: 48px;
                height: 48px;
                min-width: 48px;
                border-radius: 14px;
                object-fit: cover;
                border: 1px solid rgba(56, 189, 248, 0.35);
                box-shadow: 0 0 26px rgba(56, 189, 248, 0.18), 0 12px 26px rgba(0, 0, 0, 0.22);
            }

            .sidebar-brand-mark {
                width: 48px;
                height: 48px;
                min-width: 48px;
                display: grid;
                place-items: center;
                border-radius: 14px;
                background: linear-gradient(135deg, var(--accent), var(--accent-strong));
                box-shadow: 0 0 26px rgba(56, 189, 248, 0.18), 0 12px 26px rgba(0, 0, 0, 0.22);
            }

            .sidebar-brand-mark::before,
            .mobile-brand-mark::before {
                content: "";
                width: 62%;
                height: 62%;
                border: 3px solid #03111f;
                border-radius: 999px;
            }

            .sidebar-brand-text {
                min-width: 0;
            }

            .sidebar-brand-title {
                color: #f8fafc;
                font-size: 1.12rem;
                font-weight: 900;
                line-height: 1.05;
                overflow-wrap: anywhere;
            }

            .sidebar-brand-subtitle {
                color: #91a1b7;
                font-size: 0.78rem;
                line-height: 1.3;
                margin-top: 0.28rem;
            }

            .mobile-brand-bar {
                display: none;
                align-items: center;
                gap: 0.75rem;
                padding: 0.78rem 0;
                margin-bottom: 0.85rem;
                border-bottom: 1px solid var(--panel-border);
            }

            .mobile-brand-logo,
            .mobile-brand-mark {
                width: 42px;
                height: 42px;
                min-width: 42px;
                border-radius: 12px;
                box-shadow: 0 0 22px rgba(56, 189, 248, 0.18), 0 10px 22px rgba(0, 0, 0, 0.2);
            }

            .mobile-brand-logo {
                object-fit: cover;
                border: 1px solid rgba(56, 189, 248, 0.35);
            }

            .mobile-brand-mark {
                display: grid;
                place-items: center;
                background: linear-gradient(135deg, var(--accent), var(--accent-strong));
            }

            .mobile-brand-title {
                color: #f8fafc;
                font-size: 1rem;
                font-weight: 900;
                line-height: 1.05;
            }

            .mobile-brand-subtitle {
                color: var(--muted);
                font-size: 0.74rem;
                line-height: 1.25;
                margin-top: 0.2rem;
            }

            [data-testid="stHeader"] {
                background: rgba(8, 13, 23, 0);
            }

            .block-container {
                max-width: 1440px;
                padding-top: 2rem;
                padding-bottom: 4rem;
            }

            .hero {
                padding: 2rem;
                border: 1px solid var(--panel-border);
                border-radius: 18px;
                background:
                    linear-gradient(135deg, rgba(56, 189, 248, 0.16), rgba(34, 197, 94, 0.08)),
                    rgba(16, 24, 39, 0.84);
                box-shadow: var(--shadow);
                margin-bottom: 1.2rem;
                animation: fadeSlideUp 720ms ease-out both;
                backdrop-filter: blur(18px);
            }

            .hero-kicker {
                color: var(--accent);
                font-size: 0.76rem;
                font-weight: 800;
                letter-spacing: 0.12rem;
                text-transform: uppercase;
                margin-bottom: 0.5rem;
            }

            .hero h1 {
                color: #f8fafc;
                font-size: clamp(2rem, 4vw, 4rem);
                line-height: 1;
                margin: 0 0 0.8rem 0;
            }

            .hero p {
                max-width: 760px;
                color: var(--muted);
                font-size: 1.02rem;
                margin: 0;
            }

            .metric-card,
            .panel {
                border: 1px solid var(--panel-border);
                border-radius: 14px;
                background: rgba(16, 24, 39, 0.86);
                box-shadow: 0 14px 40px rgba(0, 0, 0, 0.22);
                backdrop-filter: blur(18px);
            }

            .metric-card {
                min-height: 126px;
                padding: 1rem;
                opacity: 0;
                transform: translateY(18px);
                animation: fadeSlideUp 620ms ease-out both;
                transition: transform 300ms ease, box-shadow 300ms ease, border-color 300ms ease;
            }

            .metric-card:hover,
            .panel:hover,
            .summary-item:hover {
                transform: translateY(-3px);
                border-color: rgba(56, 189, 248, 0.45);
                box-shadow: 0 20px 55px rgba(8, 145, 178, 0.18);
            }

            .stagger-1 { animation-delay: 80ms; }
            .stagger-2 { animation-delay: 180ms; }
            .stagger-3 { animation-delay: 280ms; }
            .stagger-4 { animation-delay: 380ms; }

            .panel {
                animation: fadeSlideUp 560ms ease-out both;
                transition: transform 300ms ease, box-shadow 300ms ease, border-color 300ms ease;
            }

            .metric-icon {
                display: inline-flex;
                width: 2.25rem;
                height: 2.25rem;
                align-items: center;
                justify-content: center;
                border-radius: 10px;
                background: rgba(56, 189, 248, 0.14);
                color: var(--accent);
                font-weight: 900;
                margin-bottom: 0.7rem;
            }

            .metric-label {
                color: var(--muted);
                font-size: 0.78rem;
                font-weight: 800;
                letter-spacing: 0.08rem;
                text-transform: uppercase;
            }

            .metric-value {
                color: #f8fafc;
                font-size: 1.6rem;
                font-weight: 800;
                margin-top: 0.3rem;
            }

            .metric-help {
                color: var(--muted);
                font-size: 0.84rem;
                margin-top: 0.2rem;
            }

            .panel {
                padding: 1.25rem;
                margin-bottom: 1rem;
            }

            .panel-title {
                display: flex;
                align-items: center;
                gap: 0.65rem;
                color: #f8fafc;
                font-size: 1.02rem;
                font-weight: 800;
                margin-bottom: 0.9rem;
            }

            .panel-title span {
                display: inline-flex;
                width: 2rem;
                height: 2rem;
                align-items: center;
                justify-content: center;
                border-radius: 9px;
                background: rgba(56, 189, 248, 0.13);
                color: var(--accent);
                font-size: 0.82rem;
                font-weight: 900;
            }

            .badge-row {
                display: flex;
                flex-wrap: wrap;
                gap: 0.55rem;
                margin: 0.7rem 0 0.2rem;
            }

            .badge {
                display: inline-flex;
                align-items: center;
                border-radius: 999px;
                border: 1px solid transparent;
                padding: 0.36rem 0.68rem;
                font-size: 0.78rem;
                font-weight: 800;
                transition: transform 300ms ease, box-shadow 300ms ease, border-color 300ms ease;
            }

            .badge:hover {
                transform: translateY(-1px);
            }

            .badge-ok {
                color: #bbf7d0;
                background: rgba(34, 197, 94, 0.14);
                border-color: rgba(34, 197, 94, 0.3);
            }

            .badge-warn {
                color: #fde68a;
                background: rgba(245, 158, 11, 0.14);
                border-color: rgba(245, 158, 11, 0.32);
            }

            .badge-danger {
                color: #fecdd3;
                background: rgba(244, 63, 94, 0.14);
                border-color: rgba(244, 63, 94, 0.32);
            }

            .badge-neutral {
                color: #dbeafe;
                background: rgba(96, 165, 250, 0.12);
                border-color: rgba(96, 165, 250, 0.24);
            }

            .summary-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 0.85rem;
            }

            .analytics-grid {
                display: grid;
                gap: 1rem;
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                margin-bottom: 1rem;
            }

            .insight-panel {
                display: grid;
                gap: 1rem;
                grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
                margin-top: 1rem;
            }

            .insight-card {
                border-radius: 18px;
                background: rgba(15, 23, 42, 0.88);
                border: 1px solid rgba(148, 163, 184, 0.14);
                padding: 1.2rem;
                transition: transform 260ms ease, box-shadow 260ms ease, border-color 260ms ease;
                box-shadow: 0 14px 40px rgba(0, 0, 0, 0.18);
            }

            .insight-card:hover {
                transform: translateY(-4px);
                box-shadow: 0 20px 55px rgba(56, 189, 248, 0.16);
                border-color: rgba(56, 189, 248, 0.3);
            }

            .insight-card-title {
                color: var(--muted);
                letter-spacing: 0.08em;
                text-transform: uppercase;
                font-size: 0.8rem;
                margin-bottom: 0.5rem;
            }

            .insight-card-value {
                color: #f8fafc;
                font-size: 1.8rem;
                font-weight: 800;
                margin-bottom: 0.35rem;
            }

            .insight-card-copy {
                color: var(--muted);
                font-size: 0.95rem;
                line-height: 1.6;
            }

            .plot-card {
                border-radius: 18px;
                padding: 1rem;
                border: 1px solid rgba(148, 163, 184, 0.12);
                background: rgba(16, 24, 39, 0.9);
                box-shadow: 0 14px 40px rgba(0, 0, 0, 0.16);
                transition: transform 260ms ease, box-shadow 260ms ease;
            }

            .plot-card:hover {
                transform: translateY(-3px);
                box-shadow: 0 18px 44px rgba(8, 145, 178, 0.14);
            }

            .empty-state {
                padding: 1.25rem;
                border: 1px dashed rgba(148, 163, 184, 0.28);
                border-radius: 14px;
                color: var(--muted);
                background: rgba(15, 23, 42, 0.46);
            }

            .image-preview-frame {
                animation: zoomInSoft 620ms ease-out both;
                border-radius: 14px;
                overflow: hidden;
                border: 1px solid rgba(56, 189, 248, 0.22);
                box-shadow: 0 16px 44px rgba(2, 132, 199, 0.12);
            }

            .summary-item:hover {
                transform: translateY(-3px);
                border-color: rgba(56, 189, 248, 0.38);
                background: rgba(15, 23, 42, 0.78);
                box-shadow: 0 18px 42px rgba(8, 145, 178, 0.14);
                text-transform: uppercase;
                margin-bottom: 0.25rem;
            }

            .summary-value {
                color: var(--text);
                font-weight: 700;
                overflow-wrap: anywhere;
            }

            .empty-state {
                padding: 1.25rem;
                border: 1px dashed rgba(148, 163, 184, 0.28);
                border-radius: 14px;
                color: var(--muted);
                background: rgba(15, 23, 42, 0.46);
            }

            .image-preview-frame {
                animation: zoomInSoft 620ms ease-out both;
                border-radius: 14px;
                overflow: hidden;
                border: 1px solid rgba(56, 189, 248, 0.22);
                box-shadow: 0 16px 44px rgba(2, 132, 199, 0.12);
            }

            .verification-badge {
                display: inline-flex;
                align-items: center;
                gap: 0.45rem;
                margin: 0.7rem 0 0.3rem;
                padding: 0.52rem 0.85rem;
                border-radius: 999px;
                font-size: 0.82rem;
                font-weight: 900;
                border: 1px solid transparent;
            }

            .verification-badge::before {
                content: "";
                width: 0.58rem;
                height: 0.58rem;
                border-radius: 999px;
                background: currentColor;
            }

            .verify-pending {
                color: #fde68a;
                background: rgba(245, 158, 11, 0.13);
                border-color: rgba(245, 158, 11, 0.34);
                animation: pulseYellow 1.4s ease-in-out infinite;
            }

            .verify-processing {
                color: #bae6fd;
                background: rgba(14, 165, 233, 0.14);
                border-color: rgba(14, 165, 233, 0.36);
                animation: pulseBlue 1.1s ease-in-out infinite;
            }

            .verify-verified {
                color: #bbf7d0;
                background: rgba(34, 197, 94, 0.16);
                border-color: rgba(34, 197, 94, 0.38);
                box-shadow: 0 0 28px rgba(34, 197, 94, 0.25);
            }

            .verify-review {
                color: #fed7aa;
                background: rgba(249, 115, 22, 0.14);
                border-color: rgba(249, 115, 22, 0.36);
                box-shadow: 0 0 28px rgba(249, 115, 22, 0.2);
            }

            .verify-rejected {
                color: #fecdd3;
                background: rgba(244, 63, 94, 0.14);
                border-color: rgba(244, 63, 94, 0.36);
                box-shadow: 0 0 28px rgba(244, 63, 94, 0.2);
            }

            .ai-loader {
                position: relative;
                min-height: 190px;
                border-radius: 18px;
                border: 1px solid rgba(56, 189, 248, 0.28);
                background:
                    linear-gradient(135deg, rgba(56, 189, 248, 0.15), rgba(34, 197, 94, 0.07)),
                    rgba(15, 23, 42, 0.86);
                overflow: hidden;
                box-shadow: 0 18px 55px rgba(2, 132, 199, 0.16);
                animation: fadeSlideUp 420ms ease-out both;
            }

            .ai-loader::before {
                content: "";
                position: absolute;
                inset: 18px;
                border-radius: 16px;
                border: 1px solid rgba(148, 163, 184, 0.18);
                background:
                    linear-gradient(90deg, transparent, rgba(56, 189, 248, 0.38), transparent);
                animation: scanLine 1.25s ease-in-out infinite;
            }

            .ai-loader-orbit {
                position: absolute;
                top: 50%;
                left: 50%;
                width: 76px;
                height: 76px;
                margin: -38px 0 0 -38px;
                border-radius: 50%;
                border: 2px solid rgba(56, 189, 248, 0.18);
                border-top-color: #38bdf8;
                border-right-color: #22c55e;
                animation: orbitSpin 1s linear infinite;
            }

            .ai-loader-copy {
                position: absolute;
                left: 1.2rem;
                right: 1.2rem;
                bottom: 1.05rem;
                color: #dbeafe;
                font-weight: 800;
                letter-spacing: 0.02rem;
            }

            .analysis-status-list {
                display: grid;
                gap: 0.55rem;
                margin-top: 1rem;
                color: #dbeafe;
                font-size: 0.94rem;
            }

            .analysis-status-step {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 0.75rem;
                padding: 0.88rem 0.95rem;
                border-radius: 16px;
                border: 1px solid rgba(148, 163, 184, 0.12);
                background: rgba(15, 23, 42, 0.58);
                transition: transform 300ms ease, border-color 300ms ease, background 300ms ease, box-shadow 300ms ease;
            }

            .analysis-status-step .step-left {
                display: inline-flex;
                align-items: center;
                gap: 0.75rem;
                min-width: 0;
            }

            .analysis-status-step .step-title {
                font-weight: 700;
                color: #e2e8f0;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }

            .analysis-status-step .step-icon {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-width: 1.3rem;
                min-height: 1.3rem;
                border-radius: 999px;
                background: rgba(148, 163, 184, 0.16);
                color: #dbeafe;
                font-size: 0.86rem;
                font-weight: 900;
            }

            .analysis-status-step.active {
                background: rgba(56, 189, 248, 0.16);
                border-color: rgba(56, 189, 248, 0.35);
                box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.18), 0 18px 48px rgba(8, 145, 178, 0.08);
                transform: translateY(-1px);
            }

            .analysis-status-step.active .step-icon {
                animation: pulseBlue 1.2s ease-in-out infinite;
            }

            .analysis-status-step.step-completed {
                background: rgba(34, 197, 94, 0.12);
                border-color: rgba(34, 197, 94, 0.3);
                color: #dcfce7;
            }

            .analysis-status-step.step-completed .step-icon {
                background: rgba(34, 197, 94, 0.24);
                color: #22c55e;
            }

            .analysis-status-step.step-completed .step-title {
                color: #d2fae3;
            }

            .step-spinner {
                width: 0.85rem;
                height: 0.85rem;
                border-radius: 50%;
                border: 2px solid rgba(56, 189, 248, 0.4);
                border-top-color: #38bdf8;
                animation: spinnerRotate 0.9s linear infinite;
            }

            .success-banner {
                position: relative;
                padding: 1rem 1.1rem;
                border-radius: 18px;
                background: rgba(22, 101, 52, 0.18);
                border: 1px solid rgba(34, 197, 94, 0.42);
                color: #d7f9e5;
                box-shadow: 0 18px 50px rgba(34, 197, 94, 0.12);
                overflow: hidden;
                margin-bottom: 1rem;
            }

            .success-banner::before,
            .success-banner::after {
                content: "";
                position: absolute;
                width: 10px;
                height: 10px;
                border-radius: 50%;
                background: rgba(34, 197, 94, 0.95);
                opacity: 0.85;
                animation: confettiBurst 1.4s ease-out forwards;
            }

            .success-banner::before {
                top: 12%;
                left: 10%;
                animation-delay: 0s;
            }

            .success-banner::after {
                top: 18%;
                left: 88%;
                animation-delay: 0.14s;
            }

            .success-banner strong {
                display: inline-block;
                margin-left: 0.5rem;
                color: #e9ffec;
            }

            .workflow-card {
                padding: 1.3rem;
                border-radius: 24px;
                border: 1px solid rgba(56, 189, 248, 0.22);
                background: linear-gradient(180deg, rgba(8, 15, 29, 0.96), rgba(7, 13, 24, 0.96));
                box-shadow: 0 28px 60px rgba(2, 42, 85, 0.32);
                animation: fadeIn 0.7s ease both;
            }

            .workflow-header {
                display: flex;
                flex-wrap: wrap;
                align-items: flex-start;
                justify-content: space-between;
                gap: 0.55rem;
                margin-bottom: 1rem;
            }

            .workflow-title {
                font-size: 1.05rem;
                font-weight: 800;
                color: #f8fafc;
            }

            .workflow-copy {
                color: #cbd5e1;
                font-size: 0.95rem;
                max-width: 72ch;
            }

            .workflow-progress-bar {
                position: relative;
                width: 100%;
                height: 14px;
                border-radius: 999px;
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(56, 189, 248, 0.16);
                overflow: hidden;
                margin-bottom: 1.15rem;
            }

            .workflow-progress-fill {
                height: 100%;
                border-radius: 999px;
                background: linear-gradient(90deg, #38bdf8, #22c55e);
                box-shadow: 0 0 24px rgba(34, 197, 94, 0.28);
                transition: width 0.45s ease;
            }

            .workflow-progress-fill.running {
                background-size: 180% 100%;
                animation: progressShimmer 1.2s linear infinite;
            }

            .workflow-steps {
                display: grid;
                gap: 0.75rem;
            }

            .workflow-step {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 1rem;
                padding: 1rem 1rem;
                border-radius: 18px;
                background: rgba(9, 14, 30, 0.82);
                border: 1px solid rgba(148, 163, 184, 0.12);
                box-shadow: 0 14px 36px rgba(0, 0, 0, 0.18);
                animation: fadeIn 0.5s ease both;
            }

            .workflow-step:nth-child(1) { animation-delay: 0ms; }
            .workflow-step:nth-child(2) { animation-delay: 40ms; }
            .workflow-step:nth-child(3) { animation-delay: 80ms; }
            .workflow-step:nth-child(4) { animation-delay: 120ms; }
            .workflow-step:nth-child(5) { animation-delay: 160ms; }
            .workflow-step:nth-child(6) { animation-delay: 200ms; }
            .workflow-step:nth-child(7) { animation-delay: 240ms; }

            .workflow-step.completed {
                border-color: rgba(34, 197, 94, 0.28);
                background: rgba(22, 163, 74, 0.12);
                box-shadow: 0 18px 40px rgba(34, 197, 94, 0.14);
            }

            .workflow-step.waiting {
                opacity: 0.78;
            }

            .workflow-step.active {
                border-color: rgba(56, 189, 248, 0.34);
                background: rgba(56, 189, 248, 0.14);
                box-shadow: 0 0 24px rgba(56, 189, 248, 0.16);
                animation: pulse 1.8s ease-in-out infinite;
            }

            .workflow-step-left {
                display: inline-flex;
                align-items: center;
                gap: 0.95rem;
                min-width: 0;
            }

            .workflow-step-number {
                width: 2.05rem;
                height: 2.05rem;
                min-width: 2.05rem;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                border-radius: 999px;
                background: rgba(15, 23, 42, 0.88);
                color: #dbeafe;
                font-weight: 900;
                box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.14);
            }

            .workflow-step.completed .workflow-step-number {
                background: #dcfce7;
                color: #134e4a;
                box-shadow: 0 0 24px rgba(34, 197, 94, 0.28);
            }

            .workflow-step.active .workflow-step-number {
                background: linear-gradient(135deg, #38bdf8, #22c55e);
                color: #03111f;
                animation: glow 1.4s ease-in-out infinite alternate;
            }

            .workflow-step-title {
                color: #e2e8f0;
                font-weight: 700;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }

            .workflow-step-status {
                color: #94e5ff;
                font-size: 0.88rem;
                font-weight: 700;
                letter-spacing: 0.01rem;
                white-space: nowrap;
            }

            .workflow-active {
                margin-top: 0.25rem;
                color: #7dd3fc;
                font-size: 0.86rem;
                font-weight: 700;
            }

            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(24px); }
                to { opacity: 1; transform: translateY(0); }
            }

            @keyframes pulse {
                0%, 100% { transform: translateY(0); box-shadow: 0 0 24px rgba(56, 189, 248, 0.12); }
                50% { transform: translateY(-1px); box-shadow: 0 0 32px rgba(56, 189, 248, 0.22); }
            }

            @keyframes progressShimmer {
                0% { background-position: 0% 50%; }
                100% { background-position: 180% 50%; }
            }

            @keyframes glow {
                from { box-shadow: 0 0 16px rgba(34, 197, 94, 0.18); }
                to { box-shadow: 0 0 30px rgba(34, 197, 94, 0.32); }
            }

            @keyframes spinnerRotate {
                to { transform: rotate(360deg); }
            }

            @keyframes confettiBurst {
                from { transform: translateY(0) scale(0.95); opacity: 0.8; }
                to { transform: translateY(-22px) scale(1.1); opacity: 0; }
            }

            @keyframes pulseBlue {
                0%, 100% { box-shadow: 0 0 0 0 rgba(56, 189, 248, 0.28); }
                50% { box-shadow: 0 0 0 9px rgba(56, 189, 248, 0); }
            }

            .result-card {
                animation: fadeSlideUp 520ms ease-out both;
            }

            .severity-high {
                border-color: rgba(244, 63, 94, 0.42);
                box-shadow: 0 0 26px rgba(244, 63, 94, 0.14);
            }

            .severity-medium {
                border-color: rgba(249, 115, 22, 0.42);
                box-shadow: 0 0 26px rgba(249, 115, 22, 0.14);
            }

            .severity-low,
            .severity-none {
                border-color: rgba(34, 197, 94, 0.42);
                box-shadow: 0 0 26px rgba(34, 197, 94, 0.14);
            }

            .pdf-workflow {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 0.8rem;
                margin: 0.75rem 0 1rem;
            }

            .pdf-step {
                padding: 0.85rem;
                border-radius: 12px;
                border: 1px solid rgba(34, 197, 94, 0.28);
                background: rgba(34, 197, 94, 0.1);
                color: #dcfce7;
                font-weight: 850;
                box-shadow: 0 12px 34px rgba(34, 197, 94, 0.1);
                animation: fadeSlideUp 500ms ease-out both;
            }

            .pdf-step:nth-child(2) { animation-delay: 100ms; }
            .pdf-step:nth-child(3) { animation-delay: 200ms; }

            .dashboard-card,
            .confidence-card,
            .risk-card,
            .explanation-card,
            .damage-card,
            .analysis-summary-card,
            .export-panel {
                padding: 1.2rem;
                border-radius: 22px;
                border: 1px solid rgba(148, 163, 184, 0.18);
                background: rgba(8, 14, 28, 0.82);
                box-shadow: 0 24px 60px rgba(2, 42, 85, 0.3);
                backdrop-filter: blur(18px);
                transition: transform 280ms ease, border-color 280ms ease, box-shadow 280ms ease;
            }

            .dashboard-card:hover,
            .confidence-card:hover,
            .risk-card:hover,
            .explanation-card:hover,
            .damage-card:hover,
            .analysis-summary-card:hover,
            .export-panel:hover {
                transform: translateY(-2px);
                border-color: rgba(56, 189, 248, 0.36);
                box-shadow: 0 28px 72px rgba(8, 145, 178, 0.22);
            }

            .card-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 0.75rem;
                margin-bottom: 1rem;
            }

            .card-title {
                font-size: 1rem;
                font-weight: 800;
                color: #f8fafc;
            }

            .card-subtitle {
                color: #94a3b8;
                font-size: 0.92rem;
            }

            .confidence-ring {
                width: 108px;
                height: 108px;
                border-radius: 50%;
                display: grid;
                place-items: center;
                background: radial-gradient(circle at top left, rgba(34, 197, 94, 0.16), transparent 38%), rgba(9, 14, 28, 0.96);
                border: 1px solid rgba(56, 189, 248, 0.16);
            }

            .confidence-ring-inner {
                width: 74px;
                height: 74px;
                border-radius: 50%;
                display: grid;
                place-items: center;
                background: rgba(15, 23, 42, 0.9);
                color: #f8fafc;
                font-weight: 800;
                font-size: 1.2rem;
            }

            .risk-badge {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                border-radius: 999px;
                padding: 0.55rem 0.95rem;
                font-weight: 800;
                letter-spacing: 0.01rem;
                background: rgba(255, 255, 255, 0.06);
                color: #f8fafc;
                border: 1px solid rgba(148, 163, 184, 0.18);
            }

            .risk-low { color: #a3e635; }
            .risk-medium { color: #f59e0b; }
            .risk-high { color: #f43f5e; }

            .risk-meter {
                width: 100%;
                height: 14px;
                border-radius: 999px;
                background: rgba(148, 163, 184, 0.15);
                overflow: hidden;
                margin: 0.85rem 0 1rem;
            }

            .risk-meter-fill {
                height: 100%;
                border-radius: 999px;
                background: linear-gradient(90deg, #22c55e, #f59e0b, #f43f5e);
                box-shadow: 0 0 22px rgba(244, 63, 94, 0.14);
                transition: width 0.5s ease;
            }

            .image-gallery {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
                gap: 0.8rem;
                margin-top: 1rem;
            }

            .image-thumb {
                border-radius: 18px;
                overflow: hidden;
                border: 1px solid rgba(56, 189, 248, 0.16);
                box-shadow: 0 14px 36px rgba(8, 145, 178, 0.1);
            }

            .image-thumb img {
                width: 100%;
                height: auto;
                display: block;
            }

            .chart-card {
                padding: 1rem;
                border-radius: 20px;
                background: rgba(12, 18, 33, 0.86);
                border: 1px solid rgba(148, 163, 184, 0.14);
                box-shadow: 0 20px 45px rgba(0, 0, 0, 0.18);
            }

            .final-decision-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 0.85rem;
                margin-top: 1rem;
            }

            .final-decision-item {
                padding: 1rem;
                border-radius: 18px;
                background: rgba(9, 14, 28, 0.82);
                border: 1px solid rgba(148, 163, 184, 0.12);
            }

            .download-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 0.85rem;
                margin-top: 1rem;
            }

            div[data-testid="stButton"] button,
            div[data-testid="stDownloadButton"] button {
                width: 100%;
                border: 0;
                border-radius: 12px;
                color: #03111f;
                background: linear-gradient(135deg, #38bdf8, #22c55e);
                font-weight: 900;
                padding: 0.72rem 1rem;
                transition: transform 300ms ease, box-shadow 300ms ease, filter 300ms ease;
                box-shadow: 0 14px 34px rgba(34, 197, 94, 0.16);
            }

            div[data-testid="stButton"] button:hover,
            div[data-testid="stDownloadButton"] button:hover {
                transform: translateY(-2px);
                filter: saturate(1.12);
                box-shadow: 0 18px 42px rgba(56, 189, 248, 0.24);
            }

            div[data-testid="stFileUploader"] {
                border-radius: 14px;
            }

            .stTextArea textarea,
            .stSelectbox div[data-baseweb="select"] > div {
                border-radius: 12px;
                border-color: rgba(148, 163, 184, 0.18);
                background: rgba(15, 23, 42, 0.7);
                color: var(--text);
                transition: border-color 300ms ease, box-shadow 300ms ease;
            }

            .stTextArea textarea:focus {
                border-color: rgba(56, 189, 248, 0.58);
                box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.12);
            }

            @keyframes fadeSlideUp {
                from {
                    opacity: 0;
                    transform: translateY(22px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }

            @keyframes zoomInSoft {
                from {
                    opacity: 0;
                    transform: scale(0.965);
                }
                to {
                    opacity: 1;
                    transform: scale(1);
                }
            }

            @keyframes pulseYellow {
                0%, 100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.24); }
                50% { box-shadow: 0 0 0 8px rgba(245, 158, 11, 0); }
            }

            @keyframes pulseBlue {
                0%, 100% { box-shadow: 0 0 0 0 rgba(56, 189, 248, 0.28); }
                50% { box-shadow: 0 0 0 9px rgba(56, 189, 248, 0); }
            }

            @keyframes scanLine {
                0% { transform: translateX(-110%); opacity: 0.2; }
                45% { opacity: 0.95; }
                100% { transform: translateX(110%); opacity: 0.2; }
            }

            @keyframes orbitSpin {
                to { transform: rotate(360deg); }
            }

            @media (max-width: 900px) {
                .block-container {
                    padding-top: 0.75rem;
                    padding-left: 1rem;
                    padding-right: 1rem;
                }

                .summary-grid {
                    grid-template-columns: 1fr;
                }

                .hero {
                    padding: 1.3rem;
                }

                .pdf-workflow {
                    grid-template-columns: 1fr;
                }

                .sidebar-brand {
                    padding-top: 0.35rem;
                }

                .sidebar-brand-logo,
                .sidebar-brand-mark {
                    width: 42px;
                    height: 42px;
                    min-width: 42px;
                    border-radius: 12px;
                }

                .sidebar-brand-title {
                    font-size: 1rem;
                }

                .sidebar-brand-subtitle {
                    font-size: 0.74rem;
                }

                .mobile-brand-bar {
                    display: flex;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar():
    logo_data_uri = get_logo_data_uri()
    if hasattr(st, "logo") and LOGO_PATH.exists():
        st.logo(str(LOGO_PATH), icon_image=str(LOGO_PATH))

    with st.sidebar:
        if logo_data_uri:
            logo_markup = f'<img class="sidebar-brand-logo" src="{logo_data_uri}" alt="{escape(APP_TITLE)} logo" />'
        else:
            logo_markup = '<div class="sidebar-brand-mark" aria-label="ClaimVision AI logo mark"></div>'
        st.markdown(
            f"""
            <div class="sidebar-brand">
                {logo_markup}
                <div class="sidebar-brand-text">
                    <div class="sidebar-brand-title">{escape(APP_TITLE)}</div>
                    <div class="sidebar-brand-subtitle">{escape(APP_SUBTITLE)}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        section = st.radio(
            "Navigation",
            [
                "Overview",
                "Analytics Dashboard",
                "Review Workspace",
                "AI Analysis",
                "Report",
            ],
            format_func=lambda value: {
                "Overview": "🏠 Overview",
                "Analytics Dashboard": "📊 Analytics Dashboard",
                "Review Workspace": "🧩 Review Workspace",
                "AI Analysis": "🤖 AI Analysis",
                "Report": "📄 Report",
            }.get(value, value),
            label_visibility="collapsed",
        )
        st.divider()
        st.markdown("### Review Mode")
        st.caption("Single-claim visual triage powered by the existing Gemini analyzer.")
        st.markdown(
            """
            <div class="badge-row">
                <span class="badge badge-ok">Live analyzer</span>
                <span class="badge badge-neutral">Streamlit UI</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    return section


def render_mobile_brand_bar():
    logo_data_uri = get_logo_data_uri()
    if logo_data_uri:
        logo_markup = f'<img class="mobile-brand-logo" src="{logo_data_uri}" alt="{escape(APP_TITLE)} logo" />'
    else:
        logo_markup = '<div class="mobile-brand-mark" aria-label="ClaimVision AI logo mark"></div>'

    st.markdown(
        f"""
        <div class="mobile-brand-bar">
            {logo_markup}
            <div>
                <div class="mobile-brand-title">{escape(APP_TITLE)}</div>
                <div class="mobile-brand-subtitle">{escape(APP_SUBTITLE)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero():
    st.markdown(
        """
        <section class="hero">
            <div class="hero-kicker">Multi-modal evidence review</div>
            <h1>Professional AI claim verification dashboard</h1>
            <p>
                Review uploaded damage evidence, inspect status signals, and export a
                concise analysis report from one polished SaaS-style workspace.
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def status_badge(label, tone="neutral"):
    return f'<span class="badge badge-{tone}">{escape(str(label))}</span>'


def render_metric_card(icon, label, value, help_text, stagger=1):
    st.markdown(
        f"""
        <div class="metric-card stagger-{stagger}">
            <div class="metric-icon">{escape(icon)}</div>
            <div class="metric-label">{escape(label)}</div>
            <div class="metric-value">{escape(str(value))}</div>
            <div class="metric-help">{escape(help_text)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def result_value(result, key, default="Pending"):
    if not result:
        return default
    value = result.get(key, default)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return ", ".join(map(str, value)) if value else "None"
    return value if value not in (None, "") else default


def quality_tone(result):
    if not result:
        return "neutral"
    if not result.get("valid_image", False):
        return "danger"
    if result.get("quality_flags"):
        return "warn"
    return "ok"


def severity_tone(severity):
    return {
        "none": "ok",
        "low": "neutral",
        "medium": "warn",
        "high": "danger",
        "unknown": "warn",
    }.get(str(severity).lower(), "neutral")


def confidence_color(score):
    if score is None:
        return "#94a3b8"
    if score <= 50:
        return "#f43f5e"
    if score <= 75:
        return "#f59e0b"
    return "#22c55e"


def risk_level_from_score(score):
    if score is None:
        return "Low"
    if score <= 40:
        return "Low"
    if score <= 70:
        return "Medium"
    return "High"


def estimate_repair_cost(claim_object, severity):
    if str(claim_object).lower() == "car":
        if severity == "high":
            return "₹15,000 – ₹40,000"
        if severity == "medium":
            return "₹7,500 – ₹18,000"
        if severity == "low":
            return "₹5,000 – ₹12,000"
        return "₹3,000 – ₹8,000"

    if str(claim_object).lower() == "laptop":
        if severity == "high":
            return "₹20,000 – ₹50,000"
        if severity == "medium":
            return "₹8,000 – ₹18,000"
        if severity == "low":
            return "₹2,000 – ₹6,000"
        return "₹1,000 – ₹3,000"

    if str(claim_object).lower() == "package":
        if severity == "high":
            return "₹3,000 – ₹8,000"
        if severity == "medium":
            return "₹1,200 – ₹3,000"
        if severity == "low":
            return "₹500 – ₹1,400"
        return "₹250 – ₹700"

    return "₹500 – ₹7,500"


def fraud_risk_score(claim_history):
    if not claim_history:
        return 24, ["Normal claim history"]

    score = 30
    reasons = []
    history_flags = str(claim_history.get("history_flags", "")).split(";")
    past_claims = int(claim_history.get("past_claim_count", 0))
    last_90 = int(claim_history.get("last_90_days_claim_count", 0))
    rejected = int(claim_history.get("rejected_claim", 0))
    manual_review = int(claim_history.get("manual_review_claim", 0))

    if past_claims >= 5:
        score += 20
        reasons.append("Multiple previous claims")
    if last_90 >= 2:
        score += 18
        reasons.append("Suspicious claim frequency")
    if rejected >= 2 or manual_review >= 2:
        score += 20
        reasons.append("Repeated object damage or review history")
    if any(flag for flag in history_flags if flag and flag != "none"):
        score += 12
        reasons.append("History flags detected")

    if score < 30:
        score = 24
    elif score > 100:
        score = 100

    if not reasons:
        reasons = ["Normal claim history"]
    return score, reasons


def generate_confidence_score(result):
    if not result:
        return None
    severity = str(result_value(result, "severity", "unknown")).lower()
    base = 64
    if not result.get("damage_visible", False):
        base = 38
    if severity == "high":
        base += 12
    elif severity == "medium":
        base += 6
    elif severity == "low":
        base += 2
    if result.get("valid_image") is False:
        base -= 18
    score = max(10, min(98, base))
    return score


def build_ai_explanation(result, claim_object, user_claim):
    if not result:
        return "The AI explanation will appear after the claim image is analyzed."
    part = result_value(result, "object_part", "unknown")
    issue = result_value(result, "issue_type", "unknown")
    severity = result_value(result, "severity", "unknown")
    visible = result.get("damage_visible", False)
    if visible:
        return (
            f"The {part.replace('_', ' ')} shows {issue.replace('_', ' ')} damage with {severity} severity. "
            "Visual evidence supports the claim and the uploaded image was assessed for validity."
        )
    return (
        f"The uploaded image does not clearly show {issue.replace('_', ' ')} on the {part.replace('_', ' ')}, "
        "so the claim evidence is weaker and may need further review."
    )


def estimate_repair_cost(claim_object, severity):
    severity = str(severity or "unknown").lower()
    object_type = str(claim_object or "unknown").lower()

    ranges = {
        "car": {
            "high": "INR 15,000-40,000",
            "medium": "INR 7,500-18,000",
            "low": "INR 5,000-12,000",
            "none": "INR 3,000-8,000",
            "unknown": "INR 3,000-8,000",
        },
        "laptop": {
            "high": "INR 20,000-50,000",
            "medium": "INR 8,000-18,000",
            "low": "INR 2,000-6,000",
            "none": "INR 1,000-3,000",
            "unknown": "INR 1,000-3,000",
        },
        "package": {
            "high": "INR 3,000-8,000",
            "medium": "INR 1,200-3,000",
            "low": "INR 500-1,400",
            "none": "INR 250-700",
            "unknown": "INR 250-700",
        },
    }

    return ranges.get(object_type, {}).get(severity, "INR 500-7,500")


def generate_confidence_score(result):
    if not result:
        return 35

    severity = str(result_value(result, "severity", "unknown")).lower()
    quality_flags = result.get("quality_flags") or []
    if isinstance(quality_flags, str):
        quality_flags = [quality_flags]

    score = 55
    score += 20 if result.get("damage_visible", False) else -18
    score += 10 if result.get("valid_image", False) else -22

    if severity == "high":
        score += 8
    elif severity == "medium":
        score += 6
    elif severity == "low":
        score += 3
    elif severity in {"none", "unknown"}:
        score -= 6

    score -= min(len(quality_flags) * 6, 18)
    return max(10, min(98, int(round(score))))


def generate_repair_guidance(claim_object, result):
    result = result or {}
    object_type = str(result.get("object_type") or claim_object or "item").lower()
    part = str(result.get("object_part") or "").replace("_", " ").strip().lower()
    issue = str(result.get("issue_type") or "").replace("_", " ").strip().lower()
    severity = str(result.get("severity") or "unknown").lower()

    if not result.get("damage_visible"):
        return ["Request clearer evidence", "Perform manual inspection"]

    if object_type == "car":
        guidance = []
        if "bumper" in part:
            guidance.append(f"{part.title()} repair")
        elif part and part != "unknown":
            guidance.append(f"{part.title()} panel repair")
        else:
            guidance.append("Body panel inspection")

        if "dent" in issue or severity in {"medium", "high"}:
            guidance.append("Dent removal")
        if issue in {"scratch", "dent"} or severity in {"low", "medium"}:
            guidance.append("Paint correction")
        if severity == "high":
            guidance.append("Replacement assessment")
    elif object_type == "laptop":
        guidance = ["Hardware diagnostics", "Exterior casing repair"]
        if severity in {"medium", "high"}:
            guidance.append("Screen or component replacement assessment")
    elif object_type == "package":
        guidance = ["Packaging inspection", "Contents damage assessment"]
        if severity in {"medium", "high"}:
            guidance.append("Replacement or refund review")
    else:
        guidance = ["Damage inspection", "Repair feasibility assessment"]

    return list(dict.fromkeys(guidance))


def ensure_analysis_result_contract(result, claim_object=None, claim_history=None, user_claim=""):
    result = dict(result or {})
    result.setdefault("object_type", claim_object or "unknown")
    result.setdefault("issue_type", "unknown")
    result.setdefault("object_part", "unknown")
    result.setdefault("damage_visible", False)
    result.setdefault("severity", "unknown")
    result.setdefault("valid_image", False)
    result.setdefault("quality_flags", [])

    confidence_score = result.get("confidence_score")
    if confidence_score in (None, "", "--"):
        confidence_score = generate_confidence_score(result)
    try:
        confidence_score = int(round(float(confidence_score)))
    except (TypeError, ValueError):
        confidence_score = generate_confidence_score(result)
    result["confidence_score"] = max(10, min(98, confidence_score))

    fraud_score = result.get("fraud_risk_score")
    risk_reasons = result.get("fraud_risk_reasons")
    if fraud_score in (None, "", "--") or not risk_reasons:
        fraud_score, risk_reasons = fraud_risk_score(claim_history)
    try:
        fraud_score = int(round(float(fraud_score)))
    except (TypeError, ValueError):
        fraud_score, risk_reasons = fraud_risk_score(claim_history)
    result["fraud_risk_score"] = max(0, min(100, fraud_score))
    fraud_risk = result.get("fraud_risk")
    if not fraud_risk or str(fraud_risk).strip().lower() == "unknown":
        fraud_risk = risk_level_from_score(result["fraud_risk_score"])
    result["fraud_risk"] = fraud_risk
    result["fraud_risk_reasons"] = risk_reasons or ["No historical risk factors identified"]

    repair_estimate = result.get("repair_estimate")
    if not repair_estimate or str(repair_estimate).strip().lower() in {"none", "unknown", "--"}:
        repair_estimate = generate_repair_guidance(claim_object, result)
    if isinstance(repair_estimate, str):
        repair_items = [item.strip() for item in repair_estimate.split(";") if item.strip()]
    else:
        repair_items = [str(item).strip() for item in repair_estimate if str(item).strip()]
    result["repair_estimate"] = repair_items or ["Repair inspection recommended"]

    estimated_cost = result.get("estimated_cost") or result.get("estimated_repair_cost")
    if not estimated_cost or str(estimated_cost).strip().lower() in {"none", "unknown", "--"}:
        estimated_cost = estimate_repair_cost(result.get("object_type") or claim_object, result.get("severity"))
    result["estimated_cost"] = estimated_cost
    result["estimated_repair_cost"] = estimated_cost
    result["ai_explanation"] = result.get("ai_explanation") or build_ai_explanation(result, claim_object, user_claim)

    return result


def store_analysis_summary(result):
    st.session_state["analysis_result"] = result
    st.session_state["confidence_score"] = result["confidence_score"]
    st.session_state["risk_score"] = result["fraud_risk_score"]
    st.session_state["risk_level"] = result["fraud_risk"]
    st.session_state["risk_reasons"] = result["fraud_risk_reasons"]
    st.session_state["cost_estimate"] = result["estimated_cost"]
    st.session_state["repair_estimate"] = result["repair_estimate"]
    st.session_state["explanation"] = result["ai_explanation"]


def build_dashboard_stats():
    stats = load_analytics_data()
    return {
        "total": stats["total"],
        "approved": stats["approved"],
        "rejected": stats["rejected"],
        "manual": stats["manual"],
        "severity": stats["severity"],
        "status": stats["status"],
        "objects": stats["objects"],
    }


def parse_risk_flags(raw_value):
    normalized = str(raw_value or "").strip()
    if not normalized:
        return "Unknown"
    flags = [part.strip().lower() for part in normalized.replace(",", ";").split(";") if part.strip()]
    for level in ["high", "medium", "low"]:
        for flag in flags:
            if level in flag:
                return level.title()
    return "; ".join({flag.title() for flag in flags}) if flags else "Unknown"


def average_severity_label(severity_counts):
    if not severity_counts:
        return "Unknown"
    lookup = {"None": 0, "Low": 1, "Medium": 2, "High": 3}
    total = sum(severity_counts.values())
    if total == 0:
        return "Unknown"
    score = sum(lookup.get(label, 0) * count for label, count in severity_counts.items()) / total
    if score >= 2.5:
        return "High"
    if score >= 1.5:
        return "Medium"
    if score > 0:
        return "Low"
    return "Unknown"


def load_analytics_data():
    try:
        with OUTPUT_CSV_PATH.open(newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            rows = [
                row
                for row in reader
                if any(value.strip() for value in row.values() if isinstance(value, str))
                and str(row.get("user_id", "")).strip().lower() != "user_id"
            ]
    except Exception:
        rows = []

    stats = {
        "total": 0,
        "approved": 0,
        "rejected": 0,
        "manual": 0,
        "high_risk": 0,
        "damage_types": {},
        "severity": {},
        "status": {},
        "fraud_risk": {},
        "objects": {},
        "confidence_total": 0,
        "confidence_count": 0,
    }

    status_map = {
        "supported": "Approved",
        "contradicted": "Rejected",
        "not_enough_information": "Rejected",
        "manual_review": "Manual Review",
        "denied": "Rejected",
    }

    for row in rows:
        stats["total"] += 1
        claim_status = str(row.get("claim_status", "")).strip().lower()
        normalized_status = status_map.get(claim_status, str(claim_status).replace("_", " ").title() or "Unknown")
        if normalized_status == "Approved":
            stats["approved"] += 1
        if normalized_status == "Rejected":
            stats["rejected"] += 1
        if normalized_status == "Manual Review":
            stats["manual"] += 1

        issue_type = str(row.get("issue_type", "Unknown")).strip().title() or "Unknown"
        severity = str(row.get("severity", "Unknown")).strip().title() or "Unknown"
        risk_flag = parse_risk_flags(row.get("risk_flags", ""))
        object_type = str(row.get("claim_object", "Unknown")).strip().title() or "Unknown"
        confidence = str(row.get("confidence_score", "")).strip()

        stats["damage_types"][issue_type] = stats["damage_types"].get(issue_type, 0) + 1
        stats["severity"][severity] = stats["severity"].get(severity, 0) + 1
        stats["status"][normalized_status] = stats["status"].get(normalized_status, 0) + 1
        stats["fraud_risk"][risk_flag] = stats["fraud_risk"].get(risk_flag, 0) + 1
        stats["objects"][object_type] = stats["objects"].get(object_type, 0) + 1

        try:
            stats["confidence_total"] += float(confidence)
            stats["confidence_count"] += 1
        except ValueError:
            pass

        if risk_flag == "High":
            stats["high_risk"] += 1

    return stats


def render_analytics_dashboard():
    stats = load_analytics_data()
    st.markdown(
        """
        <div class="panel" style="margin-bottom:1.25rem; padding: 1.5rem 1.25rem;">
            <div class="panel-title"><span>AN</span>📊 Analytics Dashboard</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if stats["total"] == 0:
        st.markdown(
            "<div class='panel'><div class='panel-title'><span>AN</span>Analytics Summary</div>",
            unsafe_allow_html=True,
        )
        st.info("No analytics data found in dataset/output.csv. Upload claims or refresh the dataset to populate the dashboard.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    high_risk_pct = round((stats["high_risk"] / stats["total"]) * 100) if stats["total"] else 0
    avg_severity = average_severity_label(stats["severity"])
    top_damage = "No damage type available"
    if stats["damage_types"]:
        top_damage = max(stats["damage_types"].items(), key=lambda item: item[1])[0]
    top_status = "Unknown"
    if stats["status"]:
        top_status = max(stats["status"].items(), key=lambda item: item[1])[0]

    if stats["total"]:
        manual_pct = round((stats["manual"] / stats["total"]) * 100)
    else:
        manual_pct = 0

    fraud_summary = (
        f"High-risk claims represent {high_risk_pct}% of all analyzed claims, pointing to a concentrated fraud signal in the dataset. "
        f"The most common damage type is {top_damage}, and {manual_pct}% of claims are routed for manual review."
    )

    kpi_html = f"""
    <div class='analytics-grid'>
        <div class='metric-card'>
            <div class='metric-icon'>📁</div>
            <div class='metric-label'>Total Claims</div>
            <div class='metric-value'>{stats['total']}</div>
            <div class='metric-help'>Records loaded from dataset/output.csv</div>
        </div>
        <div class='metric-card'>
            <div class='metric-icon'>✅</div>
            <div class='metric-label'>Approved</div>
            <div class='metric-value'>{stats['approved']}</div>
            <div class='metric-help'>Claims verified as supported</div>
        </div>
        <div class='metric-card'>
            <div class='metric-icon'>❌</div>
            <div class='metric-label'>Rejected</div>
            <div class='metric-value'>{stats['rejected']}</div>
            <div class='metric-help'>Claims flagged as rejected</div>
        </div>
        <div class='metric-card'>
            <div class='metric-icon'>⚠️</div>
            <div class='metric-label'>Manual Review</div>
            <div class='metric-value'>{stats['manual']}</div>
            <div class='metric-help'>Claims requiring additional review</div>
        </div>
        <div class='metric-card'>
            <div class='metric-icon'>🚨</div>
            <div class='metric-label'>Fraud Risk</div>
            <div class='metric-value'>{stats['high_risk']}</div>
            <div class='metric-help'>High-risk claims in the dataset</div>
        </div>
    </div>
    """
    st.markdown(kpi_html, unsafe_allow_html=True)

    chart_row = st.columns(2)
    with chart_row[0]:
        st.markdown("<div class='panel'><div class='panel-title'><span>CS</span>Claim Status Distribution</div></div>", unsafe_allow_html=True)
        status_names = list(stats["status"].keys())
        status_values = list(stats["status"].values())
        fig = px.bar(
            x=status_names,
            y=status_values,
            text=status_values,
            labels={"x": "Status", "y": "Claims"},
            template="plotly_dark",
        )
        fig.update_traces(marker_color="#22c55e", hovertemplate="%{x}: %{y}<extra></extra>")
        fig.update_layout(
            height=360,
            margin=dict(l=0, r=0, t=24, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#e5eefb",
        )
        st.plotly_chart(fig, use_container_width=True)
    with chart_row[1]:
        st.markdown("<div class='panel'><div class='panel-title'><span>SD</span>Severity Distribution</div></div>", unsafe_allow_html=True)
        severity_names = list(stats["severity"].keys())
        severity_values = list(stats["severity"].values())
        fig = px.pie(
            values=severity_values,
            names=severity_names,
            hole=0.45,
            template="plotly_dark",
        )
        fig.update_layout(
            height=360,
            margin=dict(l=0, r=0, t=24, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#e5eefb",
        )
        st.plotly_chart(fig, use_container_width=True)

    second_row = st.columns(2)
    with second_row[0]:
        st.markdown("<div class='panel'><div class='panel-title'><span>DT</span>Damage Type Distribution</div></div>", unsafe_allow_html=True)
        damage_names = list(stats["damage_types"].keys())
        damage_values = list(stats["damage_types"].values())
        fig = px.bar(
            x=damage_names,
            y=damage_values,
            text=damage_values,
            labels={"x": "Damage Type", "y": "Claims"},
            template="plotly_dark",
        )
        fig.update_traces(marker_color="#38bdf8", hovertemplate="%{x}: %{y}<extra></extra>")
        fig.update_layout(
            height=360,
            margin=dict(l=0, r=0, t=24, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#e5eefb",
        )
        st.plotly_chart(fig, use_container_width=True)
    with second_row[1]:
        st.markdown("<div class='panel'><div class='panel-title'><span>RD</span>Risk Distribution</div></div>", unsafe_allow_html=True)
        fraud_names = list(stats["fraud_risk"].keys())
        fraud_values = list(stats["fraud_risk"].values())
        fig = px.bar(
            x=fraud_names,
            y=fraud_values,
            text=fraud_values,
            labels={"x": "Risk Level", "y": "Claims"},
            template="plotly_dark",
        )
        fig.update_traces(marker_color="#f59e0b", hovertemplate="%{x}: %{y}<extra></extra>")
        fig.update_layout(
            height=360,
            margin=dict(l=0, r=0, t=24, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#e5eefb",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("<div class='insight-panel'>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class='insight-card'>
            <div class='insight-card-title'>Most common damage type</div>
            <div class='insight-card-value'>{escape(top_damage)}</div>
            <div class='insight-card-copy'>This reflects the dominant issue type found in the current output dataset.</div>
        </div>
        <div class='insight-card'>
            <div class='insight-card-title'>Average severity</div>
            <div class='insight-card-value'>{escape(avg_severity)}</div>
            <div class='insight-card-copy'>Severity is averaged across all analyzed claims to highlight risk exposure.</div>
        </div>
        <div class='insight-card'>
            <div class='insight-card-title'>Fraud trend summary</div>
            <div class='insight-card-value'>High risk {high_risk_pct}%</div>
            <div class='insight-card-copy'>{escape(fraud_summary)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        "<div class='panel'><div class='panel-title'><span>IN</span>Business Insights</div></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class='summary-grid'>
            <div class='summary-item'>
                <div class='summary-label'>Top claim status</div>
                <div class='summary-value'>{escape(top_status)}</div>
            </div>
            <div class='summary-item'>
                <div class='summary-label'>Manual review rate</div>
                <div class='summary-value'>{manual_pct}%</div>
            </div>
            <div class='summary-item'>
                <div class='summary-label'>High-risk ratio</div>
                <div class='summary-value'>{high_risk_pct}%</div>
            </div>
            <div class='summary-item'>
                <div class='summary-label'>Analytics source</div>
                <div class='summary-value'>dataset/output.csv</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def load_user_history(claim_object):
    try:
        with (REPO_ROOT / "dataset" / "user_history.csv").open(newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)
    except Exception:
        return None

    key = str(claim_object).lower()
    for row in rows:
        summary = str(row.get("history_summary", "")).lower()
        if key in summary:
            return row

    return rows[0] if rows else None


def build_export_payload(claim_object, user_claim, result, confidence_score, risk_score, cost_estimate, explanation):
    result = ensure_analysis_result_contract(result, claim_object, st.session_state.get("claim_history"), user_claim)
    return {
        "claim_object": claim_object,
        "claim_description": user_claim,
        "analysis_timestamp": datetime.utcnow().isoformat() + "Z",
        "analysis_result": result,
        "confidence_score": confidence_score if confidence_score is not None else result["confidence_score"],
        "fraud_risk_score": risk_score if risk_score is not None else result["fraud_risk_score"],
        "risk_level": result["fraud_risk"],
        "repair_estimate": result["repair_estimate"],
        "estimated_repair_cost": cost_estimate or result["estimated_cost"],
        "ai_explanation": explanation or result["ai_explanation"],
    }


def build_output_record(claim_object, user_claim, image_path, result):
    result = ensure_analysis_result_contract(
        result,
        claim_object=claim_object,
        claim_history=st.session_state.get("claim_history"),
        user_claim=user_claim,
    )
    claim_status = infer_claim_status(result).lower().replace(" ", "_")
    evidence_met = bool(result.get("damage_visible") and result.get("valid_image"))
    repair_estimate = result.get("repair_estimate") or []
    if not isinstance(repair_estimate, list):
        repair_estimate = [str(repair_estimate)]

    return {
        "analysis_timestamp": datetime.utcnow().isoformat() + "Z",
        "user_id": "streamlit_user",
        "image_paths": str(image_path or ""),
        "user_claim": user_claim or "",
        "claim_object": claim_object or result.get("object_type", "unknown"),
        "evidence_standard_met": evidence_met,
        "evidence_standard_met_reason": "Sufficient visual evidence" if evidence_met else "Insufficient visual evidence",
        "risk_flags": result.get("fraud_risk", "Low"),
        "issue_type": result.get("issue_type", "unknown"),
        "object_part": result.get("object_part", "unknown"),
        "claim_status": claim_status,
        "claim_status_justification": "Damage visible in image" if result.get("damage_visible") else "Claimed damage not observed",
        "supporting_image_ids": Path(str(image_path or "")).stem,
        "valid_image": result.get("valid_image", False),
        "severity": result.get("severity", "unknown"),
        "confidence_score": result.get("confidence_score"),
        "fraud_risk": result.get("fraud_risk", "Low"),
        "fraud_risk_score": result.get("fraud_risk_score"),
        "repair_estimate": "; ".join(repair_estimate),
        "estimated_cost": result.get("estimated_cost"),
        "final_decision": infer_claim_status(result),
    }


def append_analysis_to_output_csv(record):
    OUTPUT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "analysis_timestamp",
        "user_id",
        "image_paths",
        "user_claim",
        "claim_object",
        "evidence_standard_met",
        "evidence_standard_met_reason",
        "risk_flags",
        "issue_type",
        "object_part",
        "claim_status",
        "claim_status_justification",
        "supporting_image_ids",
        "valid_image",
        "severity",
        "confidence_score",
        "fraud_risk",
        "fraud_risk_score",
        "repair_estimate",
        "estimated_cost",
        "final_decision",
    ]
    write_header = not OUTPUT_CSV_PATH.exists() or OUTPUT_CSV_PATH.stat().st_size == 0
    with OUTPUT_CSV_PATH.open("a", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(record)


def remember_latest_claim(claim_object, user_claim, image_path, result):
    result = ensure_analysis_result_contract(
        result,
        claim_object=claim_object,
        claim_history=st.session_state.get("claim_history"),
        user_claim=user_claim,
    )
    st.session_state["latest_claim"] = {
        "claim_object": claim_object,
        "user_claim": user_claim,
        "image_path": str(image_path or ""),
        "result": result,
        "final_decision": infer_claim_status(result),
    }


def severity_class(severity):
    severity_key = str(severity).lower()
    if severity_key in {"high", "medium", "low", "none"}:
        return f"severity-{severity_key}"
    return "severity-medium"


def verification_status(result, analysis_completed):
    if not analysis_completed:
        return "Pending"
    decision = infer_claim_status(result)
    if decision == "Supported":
        return "Verified"
    if decision == "Manual Review Required":
        return "Manual Review"
    return "Rejected"


def verification_badge(status):
    css_class = {
        "Pending": "verify-pending",
        "Processing": "verify-processing",
        "Verified": "verify-verified",
        "Manual Review": "verify-review",
        "Rejected": "verify-rejected",
    }.get(status, "verify-pending")
    return f'<div class="verification-badge {css_class}">{escape(status)}</div>'


WORKFLOW_STEP_NAMES = [
    "Uploading Evidence",
    "Extracting Claim",
    "Analyzing Image",
    "Detecting Damage",
    "Verifying Evidence",
    "Generating Report",
]


def default_workflow_steps():
    return [{"label": name, "status": "waiting"} for name in WORKFLOW_STEP_NAMES]


def init_workflow_state():
    if "analysis_running" not in st.session_state:
        st.session_state["analysis_running"] = False
    if "workflow_steps" not in st.session_state:
        st.session_state["workflow_steps"] = default_workflow_steps()
    if "workflow_progress" not in st.session_state:
        st.session_state["workflow_progress"] = 0
    if "workflow_completed" not in st.session_state:
        st.session_state["workflow_completed"] = False
    if "workflow_message" not in st.session_state:
        st.session_state["workflow_message"] = "Ready to run AI evidence review."


def reset_workflow_state():
    st.session_state["analysis_running"] = False
    st.session_state["workflow_steps"] = default_workflow_steps()
    st.session_state["workflow_progress"] = 0
    st.session_state["workflow_completed"] = False
    st.session_state["workflow_message"] = "Ready to run AI evidence review."


def start_workflow():
    reset_workflow_state()
    st.session_state["analysis_running"] = True
    st.session_state["workflow_progress"] = 5
    st.session_state["workflow_steps"][0]["status"] = "running"
    st.session_state["workflow_message"] = "Uploading evidence..."


def set_workflow_step(step_name, progress, message=None):
    current_index = WORKFLOW_STEP_NAMES.index(step_name)
    for index, step in enumerate(st.session_state["workflow_steps"]):
        if index < current_index:
            step["status"] = "completed"
        elif index == current_index:
            step["status"] = "running"
        else:
            step["status"] = "waiting"
    st.session_state["analysis_running"] = True
    st.session_state["workflow_completed"] = False
    st.session_state["workflow_progress"] = progress
    st.session_state["workflow_message"] = message or f"{step_name}..."


def complete_workflow(message="The AI evidence review workflow completed successfully."):
    for step in st.session_state["workflow_steps"]:
        step["status"] = "completed"
    st.session_state["analysis_running"] = False
    st.session_state["workflow_completed"] = True
    st.session_state["workflow_progress"] = 100
    st.session_state["workflow_message"] = message


def has_workflow_to_render():
    return (
        st.session_state.get("analysis_running")
        or st.session_state.get("workflow_completed")
        or st.session_state.get("workflow_progress", 0) > 0
    )


def render_workflow_card(message=None):
    init_workflow_state()
    steps = st.session_state["workflow_steps"]
    progress = st.session_state["workflow_progress"]
    completed = st.session_state["workflow_completed"]
    active_step = next((step["label"] for step in steps if step.get("status") == "running"), None)
    display_message = message or st.session_state.get("workflow_message", "AI analysis workflow status.")

    status_items = []
    for index, step in enumerate(steps, start=1):
        status = step.get("status", "waiting")
        if status == "completed":
            state = "completed"
            icon = "&#10003;"
            status_text = "Completed"
        elif status == "running":
            state = "active"
            icon = "<span class='step-spinner'></span>"
            status_text = "Running"
        else:
            state = "waiting"
            icon = str(index)
            status_text = "Waiting"

        status_items.append(
            f"<div class=\"workflow-step {state}\">"
            f"  <div class='workflow-step-left'>"
            f"    <div class='workflow-step-number'>{icon}</div>"
            f"    <div class='workflow-step-title'>{escape(step.get('label', 'Step'))}</div>"
            f"  </div>"
            f"  <div class='workflow-step-status'>{status_text}</div>"
            f"</div>"
        )

    status_banner = ""
    if completed:
        status_banner = (
            "<div class='success-banner'>"
            "&#10003; <strong>AI Analysis Completed Successfully</strong>"
            "</div>"
        )

    active_copy = f"<div class='workflow-active'>Current step: {escape(active_step)}</div>" if active_step else ""
    fill_state = "running" if st.session_state.get("analysis_running") else ""
    html_content = textwrap.dedent(f"""
        <div class="workflow-card">
            {status_banner}
            <div class="workflow-header">
                <div>
                    <div class="workflow-title">Evidence Review Workflow</div>
                    {active_copy}
                </div>
                <div class="workflow-copy">{escape(display_message)}</div>
            </div>
            <div class="workflow-progress-bar" aria-label="Analysis progress">
                <div class="workflow-progress-fill {fill_state}" style="width: {progress}%"></div>
            </div>
            <div class="workflow-steps">
                {''.join(status_items)}
            </div>
        </div>
        """)
    st.markdown(html_content, unsafe_allow_html=True)


def render_ai_progress_panel(message, current_step=None, progress=0, completed=False):
    init_workflow_state()
    if completed:
        complete_workflow("Analysis Complete")
    elif current_step in WORKFLOW_STEP_NAMES:
        set_workflow_step(current_step, progress, message)
    else:
        st.session_state["workflow_progress"] = progress
        st.session_state["workflow_message"] = message
    render_workflow_card(message)


def render_workflow_history():
    if has_workflow_to_render():
        render_workflow_card()


def render_legacy_ai_progress_panel(message, current_step=None, progress=0, completed=False):
    step_names = [
        "Uploading Evidence",
        "Extracting Claim",
        "Analyzing Image",
        "Detecting Damage",
        "Verifying Evidence",
        "Generating Report",
        "PDF Ready",
    ]
    status_items = []
    current_index = step_names.index(current_step) if current_step in step_names else -1
    for index, name in enumerate(step_names, start=1):
        if completed or index - 1 < current_index:
            state = "completed"
            icon = "✓"
            status_text = "Completed"
        elif index - 1 == current_index:
            state = "active"
            icon = "<span class='step-spinner'></span>"
            status_text = "In progress"
        else:
            state = ""
            icon = str(index)
            status_text = "Pending"

        status_items.append(
            f"<div class=\"workflow-step {state}\">"
            f"  <div class='workflow-step-left'>"
            f"    <div class='workflow-step-number'>{icon}</div>"
            f"    <div class='workflow-step-title'>{escape(name)}</div>"
            f"  </div>"
            f"  <div class='workflow-step-status'>{status_text}</div>"
            f"</div>"
        )

    status_banner = ""
    if completed:
        status_banner = (
            "<div class='success-banner'>"
            "✅ <strong>AI Analysis Completed Successfully</strong>"
            "</div>"
        )

    html_content = textwrap.dedent(f"""
        <div class="workflow-card">
            {status_banner}
            <div class="workflow-header">
                <div class="workflow-title">Evidence Review Workflow</div>
                <div class="workflow-copy">{escape(message)}</div>
            </div>
            <div class="workflow-progress-bar" aria-label="Analysis progress">
                <div class="workflow-progress-fill" style="width: {progress}%"></div>
            </div>
            <div class="workflow-steps">
                {''.join(status_items)}
            </div>
        </div>
        """)
    st.markdown(html_content, unsafe_allow_html=True)


def render_legacy_workflow_history():
    legacy_state = None
    if not legacy_state:
        return

    steps = legacy_state.get("steps", [])
    message = legacy_state.get("message", "AI analysis completed successfully.")
    progress = legacy_state.get("progress", 100 if legacy_state.get("completed") else 0)
    completed = legacy_state.get("completed", False)

    status_items = []
    for index, step in enumerate(steps, start=1):
        status = step.get("status", "pending")
        if status == "completed":
            state = "completed"
            icon = "✓"
            status_text = "Completed"
        else:
            state = ""
            icon = str(index)
            status_text = "Pending"

        status_items.append(
            f"<div class=\"workflow-step {state}\">"
            f"  <div class='workflow-step-left'>"
            f"    <div class='workflow-step-number'>{icon}</div>"
            f"    <div class='workflow-step-title'>{escape(step.get('label', 'Step'))}</div>"
            f"  </div>"
            f"  <div class='workflow-step-status'>{status_text}</div>"
            f"</div>"
        )

    status_banner = ""
    if completed:
        status_banner = (
            "<div class='success-banner'>"
            "✅ <strong>AI Analysis Completed Successfully</strong>"
            "</div>"
        )

    html_content = textwrap.dedent(f"""
        <div class="workflow-card">
            {status_banner}
            <div class="workflow-header">
                <div class="workflow-title">Evidence Review Workflow</div>
                <div class="workflow-copy">{escape(message)}</div>
            </div>
            <div class="workflow-progress-bar" aria-label="Analysis progress">
                <div class="workflow-progress-fill" style="width: {progress}%"></div>
            </div>
            <div class="workflow-steps">
                {''.join(status_items)}
            </div>
        </div>
        """)
    st.markdown(html_content, unsafe_allow_html=True)


def clear_analysis_state():
    st.session_state["analysis_result"] = None
    st.session_state["analysis_completed"] = False
    st.session_state["pdf_report_path"] = None
    st.session_state["report_error"] = None
    st.session_state["report_success"] = False
    st.session_state["confidence_score"] = None
    st.session_state["risk_score"] = None
    st.session_state["risk_level"] = None
    st.session_state["risk_reasons"] = []
    st.session_state["explanation"] = None
    st.session_state["cost_estimate"] = None
    st.session_state["repair_estimate"] = None
    reset_workflow_state()
    st.session_state["latest_claim"] = None
    st.session_state["analysis_stage"] = ""
    st.session_state["analysis_progress"] = 0
    st.session_state["analysis_status"] = "Idle"


def render_pdf_workflow():
    st.markdown(
        """
        <div class="pdf-workflow">
            <div class="pdf-step">✓ Evidence Verified</div>
            <div class="pdf-step">✓ Report Generated</div>
            <div class="pdf-step">✓ PDF Ready</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_chatbot_widget():
    components.html(
        """
        <script>
        (() => {
            const parentDoc = window.parent?.document || document;
            const existing = parentDoc.getElementById("claimvision-chatbot-root");
            if (existing) existing.remove();

            const root = parentDoc.createElement("div");
            root.id = "claimvision-chatbot-root";
            root.innerHTML = `
                <style>
                    #claimvision-chatbot-root {
                        position: fixed;
                        right: 22px;
                        bottom: 22px;
                        z-index: 2147483000;
                        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                        color: #e5eefb;
                    }

                    #claimvision-chatbot-root * {
                        box-sizing: border-box;
                    }

                    .cv-chat-toggle {
                        width: 62px;
                        height: 62px;
                        border: 1px solid rgba(56, 189, 248, 0.42);
                        border-radius: 999px;
                        background:
                            radial-gradient(circle at 30% 20%, rgba(255, 255, 255, 0.24), transparent 28%),
                            linear-gradient(135deg, #38bdf8, #22c55e);
                        color: #03111f;
                        box-shadow: 0 22px 48px rgba(34, 197, 94, 0.22), 0 0 32px rgba(56, 189, 248, 0.24);
                        cursor: pointer;
                        display: grid;
                        place-items: center;
                        transition: transform 180ms ease, box-shadow 180ms ease;
                    }

                    .cv-chat-toggle:hover {
                        transform: translateY(-2px) scale(1.03);
                        box-shadow: 0 26px 56px rgba(34, 197, 94, 0.28), 0 0 42px rgba(56, 189, 248, 0.34);
                    }

                    .cv-chat-toggle svg {
                        width: 29px;
                        height: 29px;
                    }

                    .cv-chat-window {
                        position: absolute;
                        right: 0;
                        bottom: 78px;
                        width: min(380px, calc(100vw - 32px));
                        height: min(620px, calc(100vh - 116px));
                        min-height: 470px;
                        border: 1px solid rgba(56, 189, 248, 0.28);
                        border-radius: 18px;
                        overflow: hidden;
                        background:
                            radial-gradient(circle at top left, rgba(56, 189, 248, 0.18), transparent 17rem),
                            linear-gradient(180deg, rgba(8, 15, 29, 0.98), rgba(7, 13, 24, 0.98));
                        box-shadow: 0 30px 80px rgba(0, 0, 0, 0.44), 0 0 38px rgba(56, 189, 248, 0.16);
                        display: none;
                    }

                    .cv-chat-window.open {
                        display: flex;
                        flex-direction: column;
                        animation: cvChatIn 180ms ease-out both;
                    }

                    .cv-chat-header {
                        padding: 15px 16px;
                        display: flex;
                        align-items: center;
                        justify-content: space-between;
                        gap: 12px;
                        border-bottom: 1px solid rgba(148, 163, 184, 0.14);
                        background: rgba(15, 23, 42, 0.74);
                    }

                    .cv-chat-brand {
                        display: flex;
                        align-items: center;
                        gap: 10px;
                        min-width: 0;
                    }

                    .cv-chat-avatar {
                        width: 34px;
                        height: 34px;
                        border-radius: 11px;
                        display: grid;
                        place-items: center;
                        background: linear-gradient(135deg, #38bdf8, #22c55e);
                        box-shadow: 0 0 22px rgba(56, 189, 248, 0.28);
                    }

                    .cv-chat-avatar::before {
                        content: "";
                        width: 58%;
                        height: 58%;
                        border: 3px solid #03111f;
                        border-radius: 999px;
                    }

                    .cv-chat-title {
                        color: #f8fafc;
                        font-weight: 800;
                        font-size: 0.98rem;
                        line-height: 1.1;
                    }

                    .cv-chat-subtitle {
                        color: #91a1b7;
                        font-size: 0.78rem;
                        margin-top: 2px;
                    }

                    .cv-chat-close {
                        width: 34px;
                        height: 34px;
                        border: 1px solid rgba(148, 163, 184, 0.18);
                        border-radius: 10px;
                        background: rgba(15, 23, 42, 0.82);
                        color: #dbeafe;
                        cursor: pointer;
                        font-size: 20px;
                        line-height: 1;
                    }

                    .cv-chat-messages {
                        flex: 1;
                        overflow-y: auto;
                        padding: 16px;
                        display: flex;
                        flex-direction: column;
                        gap: 10px;
                        scrollbar-width: thin;
                        scrollbar-color: rgba(56, 189, 248, 0.45) rgba(15, 23, 42, 0.7);
                    }

                    .cv-chat-message {
                        max-width: 86%;
                        padding: 11px 12px;
                        border-radius: 14px;
                        font-size: 0.9rem;
                        line-height: 1.45;
                        overflow-wrap: anywhere;
                    }

                    .cv-chat-message.bot {
                        align-self: flex-start;
                        color: #dbeafe;
                        background: rgba(15, 23, 42, 0.88);
                        border: 1px solid rgba(56, 189, 248, 0.18);
                        border-bottom-left-radius: 5px;
                    }

                    .cv-chat-message.user {
                        align-self: flex-end;
                        color: #03111f;
                        background: linear-gradient(135deg, #38bdf8, #22c55e);
                        border-bottom-right-radius: 5px;
                        font-weight: 650;
                    }

                    .cv-chat-actions {
                        display: grid;
                        grid-template-columns: repeat(2, minmax(0, 1fr));
                        gap: 8px;
                        padding: 0 16px 14px;
                    }

                    .cv-chat-action {
                        border: 1px solid rgba(56, 189, 248, 0.22);
                        border-radius: 11px;
                        padding: 9px 10px;
                        color: #dff6ff;
                        background: rgba(56, 189, 248, 0.08);
                        cursor: pointer;
                        font-weight: 750;
                        font-size: 0.82rem;
                        transition: background 160ms ease, border-color 160ms ease, transform 160ms ease;
                    }

                    .cv-chat-action:hover {
                        transform: translateY(-1px);
                        border-color: rgba(34, 197, 94, 0.4);
                        background: rgba(34, 197, 94, 0.12);
                    }

                    .cv-chat-input-row {
                        padding: 13px;
                        display: flex;
                        gap: 8px;
                        border-top: 1px solid rgba(148, 163, 184, 0.14);
                        background: rgba(7, 17, 31, 0.92);
                    }

                    .cv-chat-input {
                        flex: 1;
                        min-width: 0;
                        border: 1px solid rgba(148, 163, 184, 0.18);
                        border-radius: 12px;
                        background: rgba(15, 23, 42, 0.9);
                        color: #e5eefb;
                        outline: none;
                        padding: 11px 12px;
                        font-size: 0.92rem;
                    }

                    .cv-chat-input:focus {
                        border-color: rgba(56, 189, 248, 0.48);
                        box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.12);
                    }

                    .cv-chat-send {
                        width: 44px;
                        border: 0;
                        border-radius: 12px;
                        background: linear-gradient(135deg, #38bdf8, #22c55e);
                        color: #03111f;
                        cursor: pointer;
                        display: grid;
                        place-items: center;
                    }

                    .cv-chat-send svg {
                        width: 18px;
                        height: 18px;
                    }

                    @keyframes cvChatIn {
                        from { opacity: 0; transform: translateY(10px) scale(0.98); }
                        to { opacity: 1; transform: translateY(0) scale(1); }
                    }

                    @media (max-width: 520px) {
                        #claimvision-chatbot-root {
                            right: 14px;
                            bottom: 14px;
                        }

                        .cv-chat-toggle {
                            width: 56px;
                            height: 56px;
                        }

                        .cv-chat-window {
                            right: -2px;
                            bottom: 68px;
                            width: calc(100vw - 24px);
                            height: min(620px, calc(100vh - 92px));
                            min-height: 430px;
                            border-radius: 16px;
                        }

                        .cv-chat-actions {
                            grid-template-columns: 1fr;
                        }
                    }
                </style>

                <section class="cv-chat-window" aria-live="polite" aria-label="ClaimVision Assistant">
                    <div class="cv-chat-header">
                        <div class="cv-chat-brand">
                            <div class="cv-chat-avatar" aria-label="ClaimVision AI"></div>
                            <div>
                                <div class="cv-chat-title">ClaimVision Assistant</div>
                                <div class="cv-chat-subtitle">Claim status, severity, risk and evidence</div>
                            </div>
                        </div>
                        <button class="cv-chat-close" type="button" aria-label="Close chat">x</button>
                    </div>
                    <div class="cv-chat-messages"></div>
                    <div class="cv-chat-actions">
                        <button class="cv-chat-action" type="button" data-prompt="Claim Status">Claim Status</button>
                        <button class="cv-chat-action" type="button" data-prompt="Severity">Severity</button>
                        <button class="cv-chat-action" type="button" data-prompt="Fraud Risk">Fraud Risk</button>
                        <button class="cv-chat-action" type="button" data-prompt="Required Documents">Required Documents</button>
                    </div>
                    <form class="cv-chat-input-row">
                        <input class="cv-chat-input" type="text" autocomplete="off" placeholder="Ask about this claim..." aria-label="Ask ClaimVision Assistant" />
                        <button class="cv-chat-send" type="submit" aria-label="Send message">
                            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                                <path d="M5 12h13M13 6l6 6-6 6" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
                            </svg>
                        </button>
                    </form>
                </section>
                <button class="cv-chat-toggle" type="button" aria-label="Open ClaimVision Assistant">
                    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <path d="M7.5 18.5 4 21v-4.5A7.5 7.5 0 0 1 5.8 4.7 9.4 9.4 0 0 1 12 2.5c4.7 0 8.5 3.2 8.5 7.2S16.7 17 12 17c-1.6 0-3.1-.3-4.5-1" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                        <path d="M8 9.5h8M8 12.5h5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                    </svg>
                </button>
            `;
            parentDoc.body.appendChild(root);

            const chatWindow = root.querySelector(".cv-chat-window");
            const toggle = root.querySelector(".cv-chat-toggle");
            const close = root.querySelector(".cv-chat-close");
            const messages = root.querySelector(".cv-chat-messages");
            const form = root.querySelector(".cv-chat-input-row");
            const input = root.querySelector(".cv-chat-input");

            const welcome = "Hi, I am ClaimVision Assistant. Ask me about claim status, severity, fraud risk or evidence requirements.";
            const cannedResponses = {
                "claim status": "I can summarize the latest claim decision once Gemini integration is connected. For now, check the AI Review and Final Decision panels for verified, rejected, or manual-review status.",
                "severity": "Severity is estimated from detected damage type, affected object part, image confidence, and claim context. Gemini can later provide a richer explanation here.",
                "fraud risk": "Fraud risk should combine image validity, user claim history, evidence completeness, and mismatch signals between the claim text and uploaded evidence.",
                "required documents": "Required evidence usually includes clear photos of the damaged item, context photos showing the full object, claim description, and any receipts or incident details required by the selected object type."
            };

            function addMessage(text, role) {
                const bubble = parentDoc.createElement("div");
                bubble.className = `cv-chat-message ${role}`;
                bubble.textContent = text;
                messages.appendChild(bubble);
                messages.scrollTop = messages.scrollHeight;
            }

            async function generateBotReply(message) {
                const normalized = message.trim().toLowerCase();
                if (cannedResponses[normalized]) return cannedResponses[normalized];

                if (normalized.includes("status")) return cannedResponses["claim status"];
                if (normalized.includes("severity")) return cannedResponses["severity"];
                if (normalized.includes("fraud") || normalized.includes("risk")) return cannedResponses["fraud risk"];
                if (normalized.includes("document") || normalized.includes("evidence") || normalized.includes("required")) {
                    return cannedResponses["required documents"];
                }

                // Future Gemini integration point:
                // return await fetch("/api/claimvision-assistant", {
                //   method: "POST",
                //   headers: { "Content-Type": "application/json" },
                //   body: JSON.stringify({ message })
                // }).then((response) => response.json()).then((data) => data.reply);
                return "I can help with claim status, severity, fraud risk, and evidence requirements. Gemini-powered claim-specific responses can be plugged into this reply function later.";
            }

            async function sendMessage(message) {
                const text = message.trim();
                if (!text) return;
                addMessage(text, "user");
                input.value = "";
                const reply = await generateBotReply(text);
                addMessage(reply, "bot");
            }

            toggle.addEventListener("click", () => {
                chatWindow.classList.toggle("open");
                toggle.setAttribute("aria-label", chatWindow.classList.contains("open") ? "Close ClaimVision Assistant" : "Open ClaimVision Assistant");
                if (chatWindow.classList.contains("open")) input.focus();
            });

            close.addEventListener("click", () => chatWindow.classList.remove("open"));

            form.addEventListener("submit", (event) => {
                event.preventDefault();
                sendMessage(input.value);
            });

            root.querySelectorAll(".cv-chat-action").forEach((button) => {
                button.addEventListener("click", () => sendMessage(button.dataset.prompt));
            });

            addMessage(welcome, "bot");
        })();
        </script>
        """,
        height=0,
        width=0,
    )


def run_verification_progress(progress_slot, loader_slot):
    steps = [
        ("Uploading Evidence", 12, "Uploading evidence..."),
        ("Extracting Claim", 26, "Extracting claim details..."),
        ("Analyzing Image", 42, "Analyzing image..."),
        ("Detecting Damage", 58, "Detecting damage..."),
        ("Verifying Evidence", 72, "Verifying evidence..."),
    ]
    progress_bar = progress_slot.progress(0, text="Initializing secure review...")
    for current_step, value, message in steps:
        loader_slot.empty()
        with loader_slot.container():
            render_ai_progress_panel(message, current_step=current_step, progress=value)
        progress_bar.progress(value, text=message)
        time.sleep(0.28)
    return progress_bar


def update_analysis_state(
    stage,
    progress,
    status="Processing",
):
    st.session_state["analysis_stage"] = stage
    st.session_state["analysis_progress"] = progress
    st.session_state["analysis_status"] = status


def render_metrics(result, uploaded_files, claim_object, user_claim):
    image_status = "Uploaded" if uploaded_files else "Waiting"
    claim_status = "Ready" if user_claim.strip() else "Draft"
    analyzer_status = "Complete" if result else "Pending"
    quality_status = result_value(result, "valid_image", "Pending")

    metric_cols = st.columns(4)
    with metric_cols[0]:
        render_metric_card("📦", "Object Type", str(claim_object).title(), "Selected claim category", 1)
    with metric_cols[1]:
        render_metric_card(
            "📷",
            "Image Evidence",
            f"{image_status} ({len(uploaded_files) if uploaded_files else 0})",
            "Upload one or more JPG/PNG images",
            2,
        )
    with metric_cols[2]:
        render_metric_card("📋", "Review Status", claim_status, "Conversation context", 3)
    with metric_cols[3]:
        render_metric_card("🤖", "AI Review", analyzer_status, f"Image valid: {quality_status}", 4)


def render_claim_summary(claim_object, user_claim, result):
    claim_object_label = escape(str(claim_object or "Unknown").title())
    issue_label = escape(str(result_value(result, "issue_type", "Pending")))
    part_label = escape(str(result_value(result, "object_part", "Pending")))
    severity_label = escape(str(result_value(result, "severity", "Pending")))
    decision_label = escape(str(infer_claim_status(result)))
    description_text = escape(user_claim if user_claim.strip() else "No claim description entered yet.")

    st.markdown(
        """
        <div class="panel">
            <div class="panel-title"><span>CS</span>📑 Claim Summary</div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="summary-grid">
            <div class="summary-item">
                <div class="summary-label">Claim Object</div>
                <div class="summary-value">{claim_object_label}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">Detected Issue</div>
                <div class="summary-value">{issue_label}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">Object Part</div>
                <div class="summary-value">{part_label}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">Severity</div>
                <div class="summary-value">{severity_label}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">Final Decision</div>
                <div class="summary-value">{decision_label}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("**Claim description**")
    st.markdown(description_text, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render_latest_claim_summary(latest_claim):
    if not latest_claim:
        st.markdown(
            """
            <div class="panel">
                <div class="panel-title"><span>LC</span>Latest Claim</div>
                <div class="empty-state">Run an AI analysis to populate the latest claim overview.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    result = latest_claim.get("result") or {}
    claim_object = latest_claim.get("claim_object", result.get("object_type", "Unknown"))
    user_claim = latest_claim.get("user_claim", "")
    severity = result.get("severity", "unknown")
    confidence_score = result.get("confidence_score", 0)
    decision = latest_claim.get("final_decision") or infer_claim_status(result)

    st.markdown(
        f"""
        <div class="panel">
            <div class="panel-title"><span>LC</span>Latest Analyzed Claim</div>
            <div class="summary-grid">
                <div class="summary-item">
                    <div class="summary-label">Claim Object</div>
                    <div class="summary-value">{escape(str(claim_object).title())}</div>
                </div>
                <div class="summary-item">
                    <div class="summary-label">Severity</div>
                    <div class="summary-value">{escape(str(severity).title())}</div>
                </div>
                <div class="summary-item">
                    <div class="summary-label">Final Decision</div>
                    <div class="summary-value">{escape(str(decision))}</div>
                </div>
                <div class="summary-item">
                    <div class="summary-label">AI Confidence</div>
                    <div class="summary-value">{escape(str(confidence_score))}%</div>
                </div>
            </div>
            <div style="margin-top: 1rem;">
                <div class="summary-label">Latest Claim Description</div>
                <div style="color: #e2e8f0; line-height: 1.65;">{escape(user_claim or "No claim description entered.")}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_dashboard_insights(stats, claim_object=None, user_claim=None, result=None):
    st.markdown(
        """
        <div class="panel">
            <div class="panel-title"><span>DS</span>Dashboard Overview</div>
        """,
        unsafe_allow_html=True,
    )

    insight_cols = st.columns(3)
    insight_cols[0].markdown(
        f"<div class='metric-card'><div class='metric-label'>Analyzed Claims</div><div class='metric-value'>{stats['total']}</div><div class='metric-help'>Claims loaded from dataset/output.csv</div></div>",
        unsafe_allow_html=True,
    )
    insight_cols[1].markdown(
        f"<div class='metric-card'><div class='metric-label'>Verified Rate</div><div class='metric-value'>{int((stats['approved'] / stats['total'] * 100) if stats['total'] else 0)}%</div><div class='metric-help'>Supported evidence fraction</div></div>",
        unsafe_allow_html=True,
    )
    insight_cols[2].markdown(
        f"<div class='metric-card'><div class='metric-label'>Manual Reviews</div><div class='metric-value'>{stats['manual']}</div><div class='metric-help'>Claims needing extra review</div></div>",
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)

    chart_cols = st.columns(2)
    with chart_cols[0]:
        st.markdown("### Severity distribution")
        severity_names = list(stats['severity'].keys())
        severity_values = list(stats['severity'].values())
        if severity_names:
            fig = px.pie(values=severity_values, names=severity_names, hole=0.5)
            fig.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No analyzed severity data available.")
    with chart_cols[1]:
        st.markdown("### Claims by status")
        status_names = list(stats['status'].keys())
        status_values = list(stats['status'].values())
        if status_names:
            fig = px.bar(x=status_names, y=status_values, text=status_values)
            fig.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            fig.update_traces(marker_color='#38bdf8')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No analyzed status data available.")


def render_image_panel(uploaded_files, latest_image_path=None):
    st.markdown(
        """
        <div class="panel">
            <div class="panel-title"><span>IP</span>Image Preview</div>
        """,
        unsafe_allow_html=True,
    )

    if uploaded_files:
        first_image = uploaded_files[0]
        image = Image.open(first_image)
        st.markdown('<div class="image-preview-frame">', unsafe_allow_html=True)
        st.image(image, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
        st.caption(f"{first_image.name} | {image.width} x {image.height}px")

        if len(uploaded_files) > 1:
            st.markdown("### Additional evidence snapshots")
            st.markdown('<div class="image-gallery">', unsafe_allow_html=True)
            for uploaded in uploaded_files[1:]:
                thumb = Image.open(uploaded)
                thumb_html = (
                    '<div class="image-thumb">'
                    f'<img src="data:image/png;base64,{base64.b64encode(uploaded.getvalue()).decode()}" />'
                    '</div>'
                )
                st.markdown(thumb_html, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
    elif latest_image_path and Path(latest_image_path).exists():
        image = Image.open(latest_image_path)
        st.markdown('<div class="image-preview-frame">', unsafe_allow_html=True)
        st.image(image, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown(
            """
            <div class="empty-state">
                Upload a claim image to preview evidence and enable AI analysis.
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


def render_analysis_panel(result, claim_object=None, final_decision=None):
    st.markdown(
        """
        <div class="panel">
            <div class="panel-title"><span>AI</span>AI Analysis</div>
        """,
        unsafe_allow_html=True,
    )

    if not result:
        st.markdown(
            """
            <div class="empty-state">
                Analysis results will appear here after running the Gemini-powered image review.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return

    result = ensure_analysis_result_contract(
        result,
        claim_object=claim_object,
        claim_history=st.session_state.get("claim_history"),
    )

    severity = result_value(result, "severity", "unknown")
    severity_css = severity_class(severity)
    flags = result.get("quality_flags", [])
    flag_badges = (
        "".join(status_badge(flag, "warn") for flag in flags)
        if flags
        else status_badge("No quality flags", "ok")
    )

    confidence_score = result.get("confidence_score", st.session_state.get("confidence_score"))
    risk_score = result.get("fraud_risk_score", st.session_state.get("risk_score"))
    risk_level = result.get("fraud_risk", st.session_state.get("risk_level"))
    cost_estimate = result.get("estimated_cost", st.session_state.get("cost_estimate"))
    repair_estimate = result.get("repair_estimate", st.session_state.get("repair_estimate", []))
    explanation = result.get("ai_explanation", st.session_state.get("explanation"))
    risk_reasons = result.get("fraud_risk_reasons", st.session_state.get("risk_reasons", []))

    if not isinstance(repair_estimate, list):
        repair_estimate = [str(repair_estimate)]
    repair_text = "; ".join(item for item in repair_estimate if item) or "Repair inspection recommended"
    if confidence_score is None:
        confidence_score = generate_confidence_score(result)
    if risk_score is None:
        risk_score = fraud_risk_score(st.session_state.get("claim_history"))[0]
    if not risk_level:
        risk_level = risk_level_from_score(risk_score)
    if not cost_estimate:
        cost_estimate = estimate_repair_cost(claim_object, severity)

    risk_score = risk_score or 0
    risk_class = 'risk-low' if risk_score <= 40 else 'risk-medium' if risk_score <= 70 else 'risk-high'

    st.markdown(
        f"""
        <div class="badge-row">
            {status_badge("Damage visible" if result.get("damage_visible") else "Damage not visible", "ok" if result.get("damage_visible") else "warn")}
            {status_badge("Valid image" if result.get("valid_image") else "Invalid image", quality_tone(result))}
            {status_badge(f"Severity: {severity}", severity_tone(severity))}
            {flag_badges}
        </div>

        <div class="final-decision-grid">
            <div class="confidence-card">
                <div class="card-header">
                    <div>
                        <div class="card-title">AI Confidence</div>
                        <div class="card-subtitle">Evidence strength estimate</div>
                    </div>
                </div>
                <div class="confidence-ring" style="border-color: {confidence_color(confidence_score)};">
                    <div class="confidence-ring-inner">{confidence_score if confidence_score is not None else '—'}%</div>
                </div>
                <p style="margin-top: 0.9rem; color: #cbd5e1;">Confidence combines detected visibility, severity, and image validity.</p>
            </div>
            <div class="risk-card">
                <div class="card-header">
                    <div>
                        <div class="card-title">Fraud Risk</div>
                        <div class="card-subtitle">Historical risk score</div>
                    </div>
                    <div class="risk-badge {risk_class}">{risk_level or risk_level_from_score(risk_score)}</div>
                </div>
                <div class="risk-meter">
                    <div class="risk-meter-fill" style="width: {risk_score or 0}%;"></div>
                </div>
                <div style="font-size: 0.88rem; color: #cbd5e1;">{escape(', '.join(risk_reasons[:2])) if risk_reasons else 'No historical risk factors identified.'}</div>
            </div>
        </div>

        <div class="analysis-summary-card" style="margin-top: 1rem;">
            <div class="card-header">
                <div>
                    <div class="card-title">Claim Insights</div>
                    <div class="card-subtitle">Explanation and repair guidance</div>
                </div>
            </div>
            <div style="color: #e2e8f0; line-height: 1.7;">{escape(explanation or '')}</div>
            <div style="margin-top: 1rem; display: grid; grid-template-columns: 1fr 1fr; gap: 0.8rem;">
                <div class="final-decision-item">
                    <div class="summary-label">Final Decision</div>
                    <div class="summary-value">{escape(str(final_decision or infer_claim_status(result)))}</div>
                </div>
                <div class="final-decision-item">
                    <div class="summary-label">Estimated Repair</div>
                    <div class="summary-value">{escape(repair_text)}</div>
                </div>
                <div class="final-decision-item">
                    <div class="summary-label">Estimated Cost</div>
                    <div class="summary-value">{escape(str(cost_estimate or estimate_repair_cost(claim_object, severity)))}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)


def infer_claim_status(result):
    if not result:
        return "Manual Review Required"
    if not result.get("valid_image", False):
        return "Manual Review Required"
    if result.get("damage_visible"):
        return "Supported"
    return "Contradicted"


def create_pdf_report(
    claim_object,
    user_claim,
    image_path,
    result,
    confidence_score,
    fraud_risk_score,
    risk_level,
    estimated_repair_cost,
    ai_explanation,
):
    return generate_pdf_report(
        claim_description=user_claim,
        claim_object=claim_object,
        image_path=image_path,
        result=result,
        claim_status=infer_claim_status(result),
        confidence_score=confidence_score,
        fraud_risk_score=fraud_risk_score,
        risk_level=risk_level,
        estimated_repair_cost=estimated_repair_cost,
        ai_explanation=ai_explanation,
    )


def save_uploaded_image(uploaded_file):
    errors = validate_uploaded_file(uploaded_file)
    if errors:
        raise ValueError("; ".join(errors))
    TEMP_IMAGE_PATH.write_bytes(uploaded_file.getbuffer())
    return str(TEMP_IMAGE_PATH)


def main():
    configure_page()
    inject_css()

    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if "auth_name" not in st.session_state:
        st.session_state["auth_name"] = ""
    if "auth_username" not in st.session_state:
        st.session_state["auth_username"] = ""
    if "authentication_status" not in st.session_state:
        st.session_state["authentication_status"] = None

    if not st.session_state.get("authenticated", False):
        render_login_page()
        st.stop()

    render_chatbot_widget()
    # --- SESSION STATE INIT ---
    init_state = [
        ("analysis_result", None),
        ("analysis_completed", False),
        ("pdf_report_path", None),
        ("report_error", None),
        ("report_success", False),
        ("confidence_score", None),
        ("risk_score", None),
        ("risk_level", None),
        ("risk_reasons", []),
        ("explanation", None),
        ("cost_estimate", None),
        ("claim_history", None),
        ("uploaded_images", []),
        ("latest_claim", None),
        ("analysis_stage", ""),
        ("analysis_progress", 0),
        ("analysis_status", "Idle"),
        ("analyzing", False),
    ]
    for key, default in init_state:
        if key not in st.session_state:
            st.session_state[key] = default
    init_workflow_state()

    active_section = render_sidebar()

    st.sidebar.markdown(f"👤 **{st.session_state.get('auth_name', '')}**")
    if st.sidebar.button("Logout", key="logout_btn", use_container_width=True):
        clear_authentication()
        st.rerun()
    if active_section in ("Overview", "Review Workspace", "AI Analysis", "Report"):
        render_mobile_brand_bar()
        render_hero()

        if has_workflow_to_render():
            st.markdown("### Latest workflow status")
            render_workflow_history()
            if st.button("Reset Analysis", use_container_width=True):
                clear_analysis_state()
                st.experimental_rerun()

        claim_object = st.sidebar.selectbox("Claim object", ["car", "laptop", "package"])
        user_claim = st.sidebar.text_area(
            "Claim description",
            placeholder="Example: The front bumper was scratched after delivery.",
            height=140,
        )
        uploaded_files = st.sidebar.file_uploader(
            "Upload evidence image",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
        )

        if uploaded_files and not isinstance(uploaded_files, list):
            uploaded_files = [uploaded_files]

        result = st.session_state["analysis_result"]
        render_metrics(result, uploaded_files, claim_object, user_claim)

        if active_section == "Overview":
            stats = build_dashboard_stats()
            latest_claim = st.session_state.get("latest_claim")
            render_dashboard_insights(
                stats,
                latest_claim.get("claim_object") if latest_claim else claim_object,
                latest_claim.get("user_claim") if latest_claim else user_claim,
                latest_claim.get("result") if latest_claim else result,
            )

        if active_section == "Overview":
            latest_claim = st.session_state.get("latest_claim")
            left_col, right_col = st.columns([0.95, 1.05])
            with left_col:
                render_latest_claim_summary(latest_claim)
            with right_col:
                latest_image_path = latest_claim.get("image_path") if latest_claim else None
                render_image_panel(uploaded_files, latest_image_path=latest_image_path)

        if active_section == "Review Workspace":
            left_col, right_col = st.columns([0.95, 1.05])
            with left_col:
                render_claim_summary(claim_object, user_claim, result)
            with right_col:
                render_image_panel(uploaded_files)

        if active_section in ("Review Workspace", "AI Analysis"):
            st.markdown("### Review Actions")
            action_cols = st.columns([0.35, 0.65])
            with action_cols[0]:
                is_analyzing = st.session_state["analyzing"]
                analyze_clicked = st.button(
                    "Analyzing image..." if is_analyzing else "Run AI Analysis",
                    disabled=not uploaded_files or is_analyzing,
                    use_container_width=True,
                )
            with action_cols[1]:
                if not uploaded_files:
                    st.info("Upload an evidence image before running analysis.")
                elif not user_claim.strip():
                    st.warning("Add a claim description for a stronger reviewer workflow.")
                else:
                    st.success("Ready for AI evidence review.")
                st.markdown(
                    verification_badge(
                        verification_status(
                            st.session_state["analysis_result"],
                            st.session_state["analysis_completed"],
                        )
                    ),
                    unsafe_allow_html=True,
                )

            if analyze_clicked and uploaded_files:
                file_errors = validate_uploaded_file(uploaded_files[0])
                if file_errors:
                    for err in file_errors:
                        st.error(err)
                else:
                    st.session_state["analyzing"] = True
                    saved_image_path = save_uploaded_image(uploaded_files[0])
                    start_workflow()
                    st.session_state["analysis_completed"] = False
                    st.session_state["pdf_report_path"] = None
                    st.session_state["report_error"] = None
                    st.session_state["report_success"] = False

                    status_slot = st.empty()
                    loader_slot = st.empty()
                    progress_slot = st.empty()
                    status_slot.markdown(verification_badge("Processing"), unsafe_allow_html=True)
                    with loader_slot.container():
                        render_workflow_card()
                    progress_bar = run_verification_progress(progress_slot, loader_slot)

                    with st.spinner("Analyzing image..."):
                        raw_result = analyze_image(saved_image_path, claim_object)
                    claim_history = load_user_history(claim_object)
                    st.session_state["claim_history"] = claim_history
                    completed_result = ensure_analysis_result_contract(
                        raw_result,
                        claim_object=claim_object,
                        claim_history=claim_history,
                        user_claim=user_claim,
                    )
                    store_analysis_summary(completed_result)
                    remember_latest_claim(claim_object, user_claim, saved_image_path, completed_result)
                    append_analysis_to_output_csv(
                        build_output_record(claim_object, user_claim, saved_image_path, completed_result)
                    )
                    st.session_state["analysis_completed"] = True
                    st.session_state["analyzing"] = False

                if st.session_state["analysis_completed"]:
                    try:
                        loader_slot.empty()
                        with loader_slot.container():
                            render_ai_progress_panel(
                                "Generating report...",
                                current_step="Generating Report",
                                progress=86,
                            )
                        progress_bar.progress(86, text="Generating report...")
                        update_analysis_state(
                            "Report generation",
                            86,
                            status="Processing",
                        )
                        st.session_state["pdf_report_path"] = create_pdf_report(
                            claim_object,
                            user_claim,
                            saved_image_path,
                            st.session_state["analysis_result"],
                            st.session_state["confidence_score"],
                            st.session_state["risk_score"],
                            st.session_state["risk_level"],
                            st.session_state["cost_estimate"],
                            st.session_state["explanation"],
                        )
                        st.session_state["report_error"] = None
                        st.session_state["report_success"] = True
                        progress_bar.progress(100, text="Analysis Complete")
                        complete_workflow()
                        status_slot.markdown(
                            verification_badge(
                                verification_status(
                                    st.session_state["analysis_result"],
                                    st.session_state["analysis_completed"],
                                )
                            ),
                            unsafe_allow_html=True,
                        )
                        loader_slot.empty()
                        with loader_slot.container():
                            render_workflow_card("Analysis Complete")
                        time.sleep(0.35)
                    except Exception as exc:
                        st.session_state["pdf_report_path"] = None
                        st.session_state["report_error"] = str(exc)
                        st.session_state["report_success"] = False
                        progress_bar.progress(100, text="Analysis Complete")
                        complete_workflow("AI analysis completed, but the PDF report could not be generated.")
                        st.session_state["analyzing"] = False
                st.rerun()

            if st.session_state["analysis_result"]:
                update_analysis_state(
                    "Ready for review",
                    100,
                    status="Complete",
                )

            render_analysis_panel(
                st.session_state["analysis_result"],
                claim_object=claim_object,
                final_decision=infer_claim_status(st.session_state["analysis_result"]),
            )

        if active_section == "Report":
            render_claim_summary(claim_object, user_claim, result)
            render_analysis_panel(result, claim_object=claim_object, final_decision=infer_claim_status(result))

        if st.session_state["analysis_completed"]:
            st.markdown("### Export")
            if st.session_state["report_success"]:
                st.success("PDF report generated successfully.")
                render_pdf_workflow()
            if st.session_state["report_error"]:
                st.warning(f"PDF report could not be generated: {st.session_state['report_error']}")

            pdf_path = st.session_state["pdf_report_path"]
            if pdf_path and os.path.exists(pdf_path):
                with open(pdf_path, "rb") as pdf_file:
                    st.download_button(
                        label="📄 Download PDF Report",
                        data=pdf_file,
                        file_name="claim_report.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
    elif active_section == "Analytics Dashboard":
        render_analytics_dashboard()


if __name__ == "__main__":
    main()
