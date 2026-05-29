import os
import json
import sqlite3
import sys
import traceback
from datetime import datetime, date
from functools import wraps

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash
from jinja2 import TemplateNotFound, ChoiceLoader, FileSystemLoader, DictLoader

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# Render pode não expor sempre a variável RENDER em todos os fluxos de deploy.
# Por isso também consideramos RENDER_SERVICE_ID e PORT como sinais de ambiente publicado.
IS_RENDER = bool(os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_ID") or os.environ.get("PORT"))

# Para demo no Render usamos /tmp para evitar problemas de permissão/escrita no filesystem
# do diretório do app. Para produção real, migrar para PostgreSQL.
if os.environ.get("DATABASE_PATH"):
    DATABASE = os.environ["DATABASE_PATH"]
elif IS_RENDER:
    DATABASE = os.path.join("/tmp", "atacarejo_insights.db")
else:
    DATABASE = os.path.join(BASE_DIR, "instance", "atacarejo_insights.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-atacarejo-insights-change-me")
app.config["DATABASE"] = DATABASE


# -----------------------------------------------------------------------------
# Templates embutidos para Render
# -----------------------------------------------------------------------------
# Em vários deploys manuais no GitHub/Render, a pasta templates/ pode não ser
# enviada junto com app.py. Quando isso acontece, o Flask/Jinja gera erros como:
# TemplateNotFound: public_home.html ou TemplateNotFound: error.html.
# Para deixar o protótipo mais estável no Render, mantemos uma cópia embutida
# dos templates principais dentro do app.py. Assim, mesmo que a pasta templates/
# não chegue ao deploy, o sistema continua abrindo.
EMBEDDED_TEMPLATES = {
  "base.html": "<!doctype html>\n<html lang=\"pt-BR\">\n<head>\n  <meta charset=\"utf-8\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n  <meta name=\"theme-color\" content=\"#5f00d2\">\n  <meta http-equiv=\"Cache-Control\" content=\"no-store, no-cache, must-revalidate, max-age=0\">\n  <meta http-equiv=\"Pragma\" content=\"no-cache\">\n  <meta http-equiv=\"Expires\" content=\"0\">\n  <title>{% block title %}Atacarejo Insights{% endblock %}</title>\n  <link rel=\"icon\" href=\"{{ url_for('static', filename='img/icon-192.png') }}\">\n  <link rel=\"stylesheet\" href=\"{{ url_for('static', filename='css/style.css') }}?v=16\">\n  <style>\n/* CSS embutido para Render quando /static não for enviado */\n:root{\n  --bg:#08070d;\n  --panel:#12101c;\n  --panel-2:#191425;\n  --line:#2b2140;\n  --text:#f5f2ff;\n  --muted:#b7a9d5;\n  --purple:#5f00d2;\n  --purple-2:#7a20ff;\n  --orange:#f89a20;\n  --danger:#ff5977;\n  --success:#40d89b;\n  --shadow:0 18px 60px rgba(0,0,0,.35);\n  --radius:22px;\n}\n*{box-sizing:border-box}\nbody{margin:0;font-family:Inter,Segoe UI,Roboto,Arial,sans-serif;background:radial-gradient(circle at top right,rgba(95,0,210,.24),transparent 38%),linear-gradient(135deg,#050407,#100b19 60%,#08070d);color:var(--text);min-height:100vh}\na{color:inherit;text-decoration:none} small{color:var(--muted)}\n.sidebar{position:fixed;inset:0 auto 0 0;width:275px;background:rgba(7,6,10,.92);border-right:1px solid var(--line);padding:24px 18px;display:flex;flex-direction:column;gap:24px;z-index:10;backdrop-filter:blur(14px)}\n.brand{display:flex;align-items:center;gap:12px;padding:12px;border-radius:20px;background:#000;border:1px solid #1d152b;box-shadow:inset 0 0 0 1px rgba(255,255,255,.025)}.brand img{width:64px;height:auto;display:block;flex:0 0 auto}.brand span{display:flex;flex-direction:column;line-height:1.05;gap:3px;color:var(--orange);font-weight:900;letter-spacing:.03em;text-transform:uppercase;font-size:13px}.brand span strong{color:#fff;font-size:15px;letter-spacing:.01em}.brand span small{color:var(--orange);font-size:10px;letter-spacing:.14em;font-weight:900}\n.sidebar nav{display:flex;flex-direction:column;gap:8px}.sidebar nav a{padding:13px 15px;border-radius:14px;color:#d7cef2;font-weight:700}.sidebar nav a:hover{background:linear-gradient(135deg,rgba(95,0,210,.32),rgba(248,154,32,.12));color:#fff}.sidebar-footer{margin-top:auto;display:flex;flex-direction:column;gap:7px;padding:14px;border:1px solid var(--line);border-radius:18px;background:rgba(255,255,255,.03)}.logout{color:var(--orange);font-weight:800;margin-top:6px}\n.main{margin-left:275px;padding:32px;min-height:100vh}.main-public{margin-left:0;padding:0}.app-footer{color:#7f739a;font-size:12px;margin-top:34px;padding:20px 0;text-align:center}\n.page-header{display:flex;justify-content:space-between;align-items:flex-start;gap:24px;margin-bottom:26px}.page-header h1{font-size:34px;line-height:1.05;margin:4px 0 8px}.page-header p{margin:0;color:var(--muted);max-width:820px}.eyebrow{letter-spacing:.2em;text-transform:uppercase;font-size:12px;font-weight:900;color:var(--orange)!important}.header-actions{display:flex;gap:10px;flex-wrap:wrap}\n.btn-primary,.btn-outline{border:none;border-radius:14px;padding:12px 16px;font-weight:900;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;gap:8px;white-space:nowrap}.btn-primary{background:linear-gradient(135deg,var(--purple),var(--purple-2) 55%,var(--orange));color:white;box-shadow:0 12px 30px rgba(95,0,210,.35)}.btn-outline{border:1px solid var(--line);background:rgba(255,255,255,.04);color:var(--text)}button.btn-outline:hover,a.btn-outline:hover{border-color:var(--orange)}\n.login-shell{min-height:100vh;display:grid;place-items:center;padding:24px}.login-card{width:min(520px,100%);background:linear-gradient(180deg,rgba(18,16,28,.96),rgba(8,7,13,.98));border:1px solid var(--line);box-shadow:var(--shadow);border-radius:30px;padding:32px}.login-logo{width:310px;max-width:100%;display:block;margin:0 auto 18px;background:#000;border-radius:26px;padding:8px;box-shadow:0 16px 42px rgba(0,0,0,.36)}.login-card h1{font-size:30px;margin:0 0 8px;text-align:center}.login-card p{text-align:center;color:var(--muted);margin:0 0 22px}.demo-box{margin-top:20px;border:1px dashed rgba(248,154,32,.45);border-radius:18px;padding:14px;display:flex;flex-direction:column;gap:6px;background:rgba(248,154,32,.07)}.demo-box span{font-size:13px;color:#e6dcf7}\n.flash-area{position:sticky;top:0;z-index:20;margin-bottom:18px}.flash{padding:13px 16px;border-radius:16px;margin-bottom:10px;border:1px solid var(--line);background:rgba(255,255,255,.06);font-weight:800}.flash.success{border-color:rgba(64,216,155,.5);color:#9ff2d0}.flash.error{border-color:rgba(255,89,119,.5);color:#ffb7c5}\n.metric-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:16px;margin-bottom:18px}.metric-grid.small{grid-template-columns:repeat(3,minmax(0,1fr))}.metric-card{background:linear-gradient(180deg,var(--panel),var(--panel-2));border:1px solid var(--line);border-radius:var(--radius);padding:20px;box-shadow:0 12px 35px rgba(0,0,0,.18);min-height:124px}.metric-card span{display:block;color:var(--muted);font-size:13px;margin-bottom:10px}.metric-card strong{font-size:27px;line-height:1.1}.metric-card.accent{border-color:rgba(248,154,32,.45);background:linear-gradient(135deg,rgba(95,0,210,.32),rgba(248,154,32,.12))}\n.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:18px 0}.panel{background:rgba(18,16,28,.88);border:1px solid var(--line);border-radius:var(--radius);padding:20px;box-shadow:0 12px 35px rgba(0,0,0,.16);overflow:hidden}.panel-title{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:14px}.panel-title h2,.panel h2{margin:0;font-size:20px}.panel-title a,.link{color:var(--orange);font-weight:900}.muted{color:var(--muted)}.smalltext{font-size:13px}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;min-width:650px}th,td{padding:13px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:middle}th{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}td{font-size:14px}.status-pill{display:inline-flex;align-items:center;border:1px solid rgba(122,32,255,.42);background:rgba(95,0,210,.18);color:#e8dcff;border-radius:999px;padding:6px 10px;font-size:12px;font-weight:900}.status-pill.done{border-color:rgba(64,216,155,.5);background:rgba(64,216,155,.12);color:#9ff2d0}\n.pipeline-row,.maturity-row,.file-row,.user-row{display:grid;grid-template-columns:minmax(0,1.4fr) 1fr auto;gap:12px;align-items:center;padding:13px 0;border-bottom:1px solid var(--line)}.pipeline-row div:first-child,.file-row div,.user-row div{display:flex;flex-direction:column;gap:4px}.progress{height:10px;background:#2a213b;border-radius:999px;overflow:hidden}.progress.big{height:14px}.progress span{display:block;height:100%;background:linear-gradient(90deg,var(--purple-2),var(--orange));border-radius:999px}.scorebar{height:10px;background:#2a213b;border-radius:999px;overflow:hidden}.scorebar i{display:block;height:100%;background:linear-gradient(90deg,var(--purple-2),var(--orange));border-radius:999px}.cards-row{display:flex;gap:12px;flex-wrap:wrap}.mini-card{min-width:220px;max-width:300px;padding:16px;border:1px solid var(--line);border-radius:18px;background:rgba(255,255,255,.04);display:flex;flex-direction:column;gap:7px}.mini-card.danger{border-color:rgba(255,89,119,.42)}.mini-card em{color:#ffb7c5;font-style:normal;font-size:12px}\n.project-card{display:grid;grid-template-columns:minmax(0,1.1fr) 1fr auto;gap:14px;align-items:center;padding:14px;border:1px solid var(--line);border-radius:18px;background:rgba(255,255,255,.035);margin-bottom:10px}.project-card div:first-child{display:flex;flex-direction:column;gap:4px}.task-list{display:flex;flex-direction:column;gap:10px}.task-item{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center;border:1px solid var(--line);border-radius:18px;background:rgba(255,255,255,.035);padding:14px}.task-item div{display:flex;flex-direction:column;gap:5px}.task-item select{min-width:150px}.note{border:1px solid var(--line);border-radius:16px;padding:13px;margin-bottom:10px;background:rgba(255,255,255,.035)}.note p{margin:8px 0 0;color:#e7dfff}.note strong,.note small{display:block}\n.form-stack{display:flex;flex-direction:column;gap:14px}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.form-grid.compact{margin-top:16px}.form-grid label,.form-stack label{display:flex;flex-direction:column;gap:7px;color:#dbcff6;font-weight:800;font-size:13px}.full{grid-column:1/-1}.form-actions{grid-column:1/-1;display:flex;justify-content:flex-end;gap:10px}.form-actions.sticky{position:sticky;bottom:10px;background:rgba(8,7,13,.8);padding:10px;border-radius:18px;border:1px solid var(--line);backdrop-filter:blur(12px)}\ninput,select,textarea{width:100%;border:1px solid var(--line);border-radius:14px;background:#0d0b14;color:var(--text);padding:12px 13px;font:inherit;outline:none}input:focus,select:focus,textarea:focus{border-color:var(--orange);box-shadow:0 0 0 3px rgba(248,154,32,.12)}textarea{resize:vertical}.inline-form{display:grid;grid-template-columns:1.3fr .8fr .8fr .8fr auto;gap:10px;margin-top:16px}.diagnostic-form{display:flex;flex-direction:column;gap:16px}.diagnostic-card{display:grid;grid-template-columns:minmax(0,1.2fr) 260px;gap:16px;border:1px solid var(--line);border-radius:20px;padding:18px;background:rgba(255,255,255,.035)}.diagnostic-card h2{margin:0 0 6px}.diagnostic-card p{margin:0;color:var(--muted)}.score-select label{display:block;margin-bottom:8px;font-weight:900;color:var(--orange)}details summary{cursor:pointer;color:var(--orange);font-weight:900}.report-cover{text-align:center}.report-cover img{max-width:320px;background:#000;border-radius:24px;margin-bottom:18px;padding:8px}\n@media (max-width:1100px){.metric-grid{grid-template-columns:repeat(2,1fr)}.grid-2{grid-template-columns:1fr}.metric-grid.small{grid-template-columns:1fr}.project-card{grid-template-columns:1fr}.inline-form{grid-template-columns:1fr 1fr}.diagnostic-card{grid-template-columns:1fr}}\n@media (max-width:780px){.sidebar{position:sticky;width:100%;height:auto;padding:12px;flex-direction:row;align-items:center;overflow:auto}.brand img{width:50px}.brand span{display:none}.sidebar nav{flex-direction:row}.sidebar nav a{white-space:nowrap;padding:10px}.sidebar-footer{display:none}.main{margin-left:0;padding:18px}.page-header{flex-direction:column}.page-header h1{font-size:27px}.metric-grid{grid-template-columns:1fr}.form-grid{grid-template-columns:1fr}.task-item,.pipeline-row,.maturity-row,.file-row,.user-row{grid-template-columns:1fr}.login-card{padding:22px}.login-logo{width:210px}}\n@media print{body{background:#fff;color:#111}.sidebar,.app-footer,.no-print,.flash-area{display:none!important}.main{margin:0;padding:0}.panel,.metric-card{box-shadow:none;border:1px solid #ddd;background:#fff;color:#111}.muted,small{color:#555}.scorebar,.progress{background:#ddd}.scorebar i,.progress span{background:#111}.page-header{page-break-after:avoid}}\n\n/* v10 - Imersões, questionários multiusuário e jornada do projeto */\n.hero-panel{background:linear-gradient(135deg,rgba(95,0,210,.18),rgba(18,16,28,.92) 55%,rgba(248,154,32,.08))}.project-card-wide{grid-template-columns:minmax(0,1.2fr) 1fr auto}.card-actions{display:flex!important;flex-direction:row!important;align-items:center;gap:10px;justify-content:flex-end}.full-btn{width:100%;margin-top:12px}.questionnaire-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.questionnaire-card{border:1px solid var(--line);background:linear-gradient(180deg,rgba(255,255,255,.045),rgba(255,255,255,.025));border-radius:20px;padding:17px;display:flex;flex-direction:column;gap:11px}.questionnaire-card h3{margin:0;font-size:19px}.questionnaire-card p{margin:0;color:var(--muted);line-height:1.45}.q-head,.response-head,.timeline-head{display:flex;align-items:center;justify-content:space-between;gap:12px}.q-area{display:inline-flex;align-items:center;border:1px solid rgba(248,154,32,.45);background:rgba(248,154,32,.10);color:#ffd49a;border-radius:999px;padding:6px 10px;font-size:12px;font-weight:900}.q-meta{display:grid;grid-template-columns:1fr;gap:5px;color:var(--muted);font-size:13px}.q-meta strong{color:var(--text)}.admin-create{margin-top:16px;border:1px solid var(--line);border-radius:18px;padding:15px;background:rgba(255,255,255,.025)}\n.timeline{position:relative;display:flex;flex-direction:column;gap:0}.timeline:before{content:\"\";position:absolute;left:14px;top:12px;bottom:12px;width:2px;background:linear-gradient(var(--purple-2),var(--orange));opacity:.55}.timeline-item{position:relative;display:grid;grid-template-columns:40px minmax(0,1fr);gap:12px;padding:0 0 16px}.timeline-dot{position:relative;z-index:1;width:30px;height:30px;border-radius:999px;background:#211735;border:2px solid var(--line);box-shadow:0 0 0 6px rgba(18,16,28,.95)}.timeline-item.done .timeline-dot{background:var(--success);border-color:rgba(64,216,155,.85)}.timeline-item.active .timeline-dot{background:var(--orange);border-color:rgba(248,154,32,.85);box-shadow:0 0 0 6px rgba(248,154,32,.08),0 0 28px rgba(248,154,32,.28)}.timeline-content{border:1px solid var(--line);border-radius:18px;background:rgba(255,255,255,.035);padding:14px}.timeline-content p{margin:8px 0 0;color:#ded5f2;line-height:1.45}.timeline-content small{display:block;margin-top:5px}.admin-timeline .timeline-content{padding:13px}.stage-edit-form{display:flex;flex-direction:column;gap:12px}.stage-edit-grid{display:grid;grid-template-columns:90px minmax(220px,1.2fr) 170px 150px 150px 120px;gap:10px;align-items:end}.stage-edit-grid label{font-size:12px;color:#dbcff6;font-weight:900;display:flex;flex-direction:column;gap:6px}.stage-edit-grid .full{grid-column:1/-1}.responses-list{display:flex;flex-direction:column;gap:12px}.response-card{border:1px solid var(--line);border-radius:18px;background:rgba(255,255,255,.035);padding:15px}.response-card p{margin:8px 0 0;line-height:1.5}.question-text{color:#ffd49a!important;font-weight:800}.questionnaire-form textarea{min-height:110px}\n@media (max-width:1200px){.questionnaire-grid{grid-template-columns:1fr}.stage-edit-grid{grid-template-columns:1fr 1fr}.project-card-wide{grid-template-columns:1fr}.card-actions{justify-content:flex-start}}\n@media (max-width:780px){.stage-edit-grid{grid-template-columns:1fr}.q-head,.response-head,.timeline-head{align-items:flex-start;flex-direction:column}.timeline-item{grid-template-columns:34px minmax(0,1fr)}.timeline:before{left:14px}.card-actions{flex-wrap:wrap}}\n\n/* v11 - Áreas dinâmicas para diagnóstico e questionários */\n.tag-cloud{display:flex;flex-wrap:wrap;gap:9px;margin-top:12px}.area-tag{display:inline-flex;align-items:center;border:1px solid rgba(122,32,255,.38);background:rgba(95,0,210,.14);color:#eee7ff;border-radius:999px;padding:7px 11px;font-size:12px;font-weight:900;line-height:1.1}.area-tag:hover{border-color:rgba(248,154,32,.65);background:rgba(248,154,32,.11);color:#ffd49a}.form-grid .muted.full{margin:0;font-size:12px;line-height:1.45}.collapsible{margin-bottom:16px}\n\n/* v12 - Jornada horizontal clicável */\n.journey-horizontal{\n  display:flex;\n  align-items:stretch;\n  gap:14px;\n  overflow-x:auto;\n  padding:10px 4px 18px;\n  scroll-snap-type:x proximity;\n  scrollbar-width:thin;\n}\n.journey-step{\n  position:relative;\n  min-width:170px;\n  max-width:230px;\n  flex:0 0 auto;\n  scroll-snap-align:start;\n  text-decoration:none;\n  color:var(--text);\n  border:1px solid var(--line);\n  border-radius:18px;\n  background:linear-gradient(180deg,rgba(255,255,255,.055),rgba(255,255,255,.025));\n  padding:15px 15px 15px 52px;\n  min-height:74px;\n  display:flex;\n  align-items:center;\n  transition:transform .18s ease, border-color .18s ease, box-shadow .18s ease, background .18s ease;\n}\n.journey-step:after{\n  content:\"\";\n  position:absolute;\n  right:-16px;\n  top:50%;\n  width:18px;\n  height:2px;\n  background:linear-gradient(90deg,var(--purple-2),var(--orange));\n  opacity:.45;\n}\n.journey-step:last-child:after{display:none}\n.journey-step:hover{\n  transform:translateY(-3px);\n  border-color:rgba(248,154,32,.6);\n  box-shadow:0 16px 34px rgba(0,0,0,.25),0 0 0 1px rgba(248,154,32,.08);\n}\n.journey-step .step-number{\n  position:absolute;\n  left:14px;\n  top:50%;\n  transform:translateY(-50%);\n  width:28px;\n  height:28px;\n  border-radius:999px;\n  display:grid;\n  place-items:center;\n  font-weight:900;\n  font-size:13px;\n  background:#211735;\n  color:#fff;\n  border:1px solid var(--line);\n}\n.journey-step strong{\n  display:block;\n  font-size:14px;\n  line-height:1.22;\n  letter-spacing:.01em;\n}\n.journey-step.done{border-color:rgba(64,216,155,.46);background:linear-gradient(180deg,rgba(64,216,155,.10),rgba(255,255,255,.025))}\n.journey-step.done .step-number{background:var(--success);border-color:rgba(64,216,155,.85);color:#06160f}\n.journey-step.active{border-color:rgba(248,154,32,.62);background:linear-gradient(180deg,rgba(248,154,32,.14),rgba(255,255,255,.026));box-shadow:0 0 28px rgba(248,154,32,.10)}\n.journey-step.active .step-number{background:var(--orange);border-color:rgba(248,154,32,.85);color:#170b00}\n.journey-step.current{border-color:rgba(125,42,255,.9);background:linear-gradient(135deg,rgba(95,0,210,.42),rgba(248,154,32,.18));box-shadow:0 0 0 2px rgba(125,42,255,.28),0 18px 42px rgba(0,0,0,.30)}\n.journey-step.current .step-number{background:linear-gradient(135deg,var(--purple-2),var(--orange));border-color:transparent;color:#fff}\n.journey-hint{margin:0;color:var(--muted);font-size:13px;line-height:1.4}.admin-journey{margin-bottom:4px}.stage-admin-editor{margin-top:16px}.stage-editor-list{display:flex;flex-direction:column;gap:14px;margin-top:14px}.stage-focus-card .panel-title{align-items:flex-start}.stage-detail-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:14px 0}.stage-detail-grid div{border:1px solid var(--line);border-radius:16px;background:rgba(255,255,255,.035);padding:13px}.stage-detail-grid span{display:block;color:var(--muted);font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.06em;margin-bottom:5px}.stage-detail-grid strong{display:block;color:var(--text);font-size:16px}.stage-description-box{border:1px solid rgba(125,42,255,.35);border-radius:18px;background:rgba(95,0,210,.08);padding:16px;margin-top:14px}.stage-description-box h3{margin:0 0 8px}.stage-description-box p,.readable-text{line-height:1.6;color:#ded5f2}.notes-list{display:flex;flex-direction:column;gap:12px}.note-card{border:1px solid var(--line);border-radius:16px;background:rgba(255,255,255,.035);padding:14px}.note-card small{display:block;color:var(--muted);margin:4px 0 8px}.note-card p{margin:0;line-height:1.5;color:#ded5f2}\n@media (max-width:780px){.journey-step{min-width:150px;max-width:190px;padding:13px 12px 13px 46px}.journey-step strong{font-size:13px}.stage-detail-grid{grid-template-columns:1fr}}\n\n/* v13 - Ambiente institucional no portal do cliente */\n.about-hero{\n  border:1px solid rgba(248,154,32,.20);\n  background:linear-gradient(135deg,rgba(95,0,210,.22),rgba(18,16,28,.58) 55%,rgba(248,154,32,.10));\n  border-radius:28px;\n  padding:24px;\n  box-shadow:0 18px 60px rgba(0,0,0,.20);\n}\n.about-hero h1{max-width:980px;font-size:39px}\n.about-callout{\n  display:flex;\n  align-items:center;\n  justify-content:space-between;\n  gap:22px;\n  margin-bottom:18px;\n  background:linear-gradient(135deg,rgba(95,0,210,.26),rgba(18,16,28,.92) 62%,rgba(248,154,32,.11));\n  border-color:rgba(248,154,32,.26);\n}\n.about-callout h2{margin:0 0 8px;font-size:22px}.about-callout p{margin:0;color:var(--muted);line-height:1.5;max-width:850px}\n.about-intro{display:grid;grid-template-columns:320px minmax(0,1fr);gap:28px;align-items:center}.about-logo-box{border:1px solid rgba(248,154,32,.20);border-radius:28px;background:#000;display:grid;place-items:center;min-height:240px;padding:24px;box-shadow:inset 0 0 0 1px rgba(255,255,255,.025)}.about-logo-box img{max-width:100%;height:auto;display:block}.about-intro h2{font-size:27px;line-height:1.14;margin:0 0 12px}.insight-card{position:relative;min-height:235px}.insight-card h2{font-size:22px;line-height:1.18;margin:32px 0 12px}.insight-card p{line-height:1.6;color:#ded5f2;margin:0 0 16px}.insight-card small{display:block;border-top:1px solid var(--line);padding-top:12px}.insight-number{position:absolute;top:16px;right:18px;color:rgba(248,154,32,.85);font-weight:900;letter-spacing:.14em}.pillar-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.pillar-card{border:1px solid var(--line);border-radius:20px;background:rgba(255,255,255,.035);padding:17px}.pillar-card span{width:34px;height:34px;border-radius:12px;background:linear-gradient(135deg,var(--purple-2),var(--orange));display:grid;place-items:center;font-weight:900;margin-bottom:14px}.pillar-card h3{font-size:18px;margin:0 0 9px}.pillar-card p{margin:0;color:#ded5f2;line-height:1.5}.method-steps{display:flex;flex-direction:column;gap:10px}.method-step{display:grid;grid-template-columns:40px minmax(0,1fr);align-items:center;gap:12px;border:1px solid var(--line);border-radius:16px;background:rgba(255,255,255,.035);padding:12px}.method-step span{width:30px;height:30px;border-radius:999px;background:rgba(248,154,32,.14);border:1px solid rgba(248,154,32,.36);color:#ffd49a;display:grid;place-items:center;font-weight:900}.method-step strong{font-size:14px}.accent-panel{background:linear-gradient(135deg,rgba(95,0,210,.30),rgba(18,16,28,.95) 58%,rgba(248,154,32,.12));border-color:rgba(122,32,255,.35)}.accent-panel h2{font-size:25px;line-height:1.18}.case-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.case-card{border:1px solid var(--line);border-radius:20px;background:linear-gradient(180deg,rgba(255,255,255,.045),rgba(255,255,255,.022));padding:17px}.case-card h3{font-size:21px;margin:0 0 12px;color:#ffd49a}.case-card p{margin:0 0 10px;line-height:1.55;color:#ded5f2}.case-card p:last-child{margin-bottom:0}.reference-list{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:14px}.reference-list span{display:inline-flex;border:1px solid rgba(122,32,255,.38);background:rgba(95,0,210,.13);border-radius:999px;padding:8px 12px;font-weight:800;font-size:12px;color:#eee7ff}.references-panel{border-color:rgba(248,154,32,.18)}\n@media (max-width:1200px){.pillar-grid,.case-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.about-intro{grid-template-columns:1fr}.about-logo-box{min-height:180px}.about-logo-box img{max-width:320px}.about-callout{align-items:flex-start;flex-direction:column}}\n@media (max-width:780px){.about-hero h1{font-size:28px}.pillar-grid,.case-grid{grid-template-columns:1fr}.about-intro{gap:18px}.about-logo-box{min-height:150px}.about-intro h2{font-size:23px}.insight-card{min-height:auto}.about-callout .btn-primary{width:100%}}\n\n/* v14 - Site público, captação de leads, aprovações e tarefas avançadas */\n.public-nav{position:sticky;top:0;z-index:30;display:flex;align-items:center;justify-content:space-between;gap:18px;padding:18px 34px;background:rgba(5,4,7,.72);backdrop-filter:blur(14px);border-bottom:1px solid var(--line)}\n.public-nav .public-brand{display:flex;align-items:center}.public-nav img{height:58px;max-width:260px;object-fit:contain;background:#000;border-radius:18px;padding:6px}.public-nav div{display:flex;align-items:center;gap:16px;flex-wrap:wrap}.public-nav a{font-weight:900;color:#e8dcff}.public-nav a:hover{color:#ffd49a}\n.public-hero{display:grid;grid-template-columns:minmax(0,1.2fr) 420px;gap:32px;align-items:center;padding:72px 42px 38px;max-width:1280px;margin:0 auto}.public-hero h1{font-size:54px;line-height:1.02;margin:8px 0 18px;letter-spacing:-.04em}.public-hero p{font-size:18px;line-height:1.6;color:#ded5f2;max-width:850px}.public-actions{display:flex;gap:14px;flex-wrap:wrap;margin-top:28px}.public-hero-card{border:1px solid rgba(248,154,32,.22);border-radius:32px;background:linear-gradient(180deg,rgba(18,16,28,.95),rgba(10,8,16,.94));box-shadow:var(--shadow);padding:28px}.public-hero-card img{display:block;width:100%;background:#000;border-radius:24px;padding:10px;margin-bottom:24px}.public-hero-card h2{font-size:29px;line-height:1.1;margin:0 0 10px}.public-hero-card p{font-size:15px;margin:0;color:var(--muted)}\n.public-section{max-width:1280px;margin:0 auto;padding:34px 42px}.section-title{margin-bottom:22px}.section-title h2{font-size:34px;line-height:1.08;margin:0 0 10px;max-width:880px}.section-title p{color:var(--muted);line-height:1.55;max-width:920px}.public-grid-3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}.public-cta{max-width:1180px;margin:36px auto 24px;padding:36px;border-radius:32px;border:1px solid rgba(248,154,32,.30);background:linear-gradient(135deg,rgba(95,0,210,.35),rgba(248,154,32,.12));text-align:center}.public-cta h2{font-size:34px;line-height:1.1;margin:0 auto 12px;max-width:850px}.public-cta p{color:#ded5f2;max-width:760px;margin:0 auto 22px;line-height:1.55}.register-shell{min-height:calc(100vh - 110px);display:grid;place-items:start center;padding:34px}.register-panel{width:min(980px,100%)}.register-panel h1{font-size:34px;line-height:1.1;margin:0 0 12px}.lead-actions{display:flex;gap:8px;margin:8px 0;align-items:center}.lead-actions input,.lead-actions select{min-width:130px}.approval-list{display:flex;flex-direction:column;gap:14px}.approval-card{border:1px solid var(--line);border-radius:20px;background:rgba(255,255,255,.035);padding:16px}.approval-card.small-card{padding:13px}.approval-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:12px}.approval-head strong{display:block}.approval-head small{display:block;margin-top:4px}.approval-values{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:12px 0}.approval-values div{border:1px solid var(--line);border-radius:16px;background:#0d0b14;padding:12px;overflow:auto}.approval-values span{display:block;color:var(--muted);font-size:12px;text-transform:uppercase;font-weight:900;margin-bottom:6px}.approval-values p{margin:0;white-space:pre-wrap;line-height:1.45}.approval-actions{display:grid;grid-template-columns:1fr auto;gap:10px;margin-top:10px}.status-pill.warning{border-color:rgba(248,154,32,.55);background:rgba(248,154,32,.14);color:#ffd49a}.status-pill.danger{border-color:rgba(255,89,119,.55);background:rgba(255,89,119,.12);color:#ffb7c5}.status-pill.muted-pill{border-color:rgba(183,169,213,.25);background:rgba(183,169,213,.08);color:#c9bedf}.approval-summary{border-color:rgba(248,154,32,.24)}.compact-list{max-height:680px;overflow:auto}.task-detailed{grid-template-columns:minmax(0,1fr) minmax(220px,300px);align-items:start}.task-side{display:flex;flex-direction:column;gap:10px;align-items:stretch}.task-status-form{display:flex;flex-direction:column;gap:8px}.task-status-form input,.task-status-form select{font-size:13px}.task-edit-details{border:1px solid var(--line);border-radius:14px;padding:10px;background:rgba(255,255,255,.025)}.compact-stack{gap:9px;margin-top:10px}.compact-stack label{font-size:12px}.compact-stack input,.compact-stack select,.compact-stack textarea{padding:9px 10px;font-size:13px}.task-list-detailed .task-item div small{line-height:1.35}.form-grid .btn-primary,.form-grid .btn-outline{min-height:44px}\n@media (max-width:1100px){.public-hero{grid-template-columns:1fr}.public-hero-card{max-width:560px}.public-grid-3{grid-template-columns:1fr}.public-nav{align-items:flex-start;flex-direction:column}.public-hero h1{font-size:40px}.task-detailed{grid-template-columns:1fr}.approval-values{grid-template-columns:1fr}}\n@media (max-width:780px){.public-nav{padding:14px 18px}.public-nav div{gap:10px}.public-nav img{height:46px}.public-hero,.public-section{padding-left:18px;padding-right:18px}.public-hero h1{font-size:33px}.section-title h2,.public-cta h2{font-size:27px}.public-actions .btn-primary,.public-actions .btn-outline,.public-nav .btn-primary,.public-nav .btn-outline{width:100%}.lead-actions,.approval-actions{grid-template-columns:1fr;display:grid}.register-shell{padding:18px}}\n\n/* v15 - Cadastro simplificado, perfis de acesso e governança de usuários */\n.muted-note{border:1px solid rgba(248,154,32,.22);background:rgba(248,154,32,.08);color:#f4ddbd;border-radius:16px;padding:12px 14px;line-height:1.45;margin:14px 0}\n.permission-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.permission-grid h3{margin:0 0 10px;color:#ffd49a}.permission-card{border:1px solid var(--line);background:rgba(255,255,255,.035);border-radius:16px;padding:13px;margin-bottom:10px}.permission-card strong{display:block}.permission-card span{display:inline-flex;margin:7px 0;border:1px solid rgba(122,32,255,.4);border-radius:999px;padding:4px 8px;color:#eee7ff;font-size:12px;font-weight:900}.permission-card p{margin:0;color:var(--muted);line-height:1.45;font-size:13px}.user-admin-list{display:flex;flex-direction:column;gap:16px}.user-admin-card{border:1px solid var(--line);border-radius:22px;background:linear-gradient(180deg,rgba(255,255,255,.045),rgba(255,255,255,.022));padding:16px}.user-admin-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}.user-admin-head strong,.user-admin-head small{display:block}.user-admin-head div:last-child{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.user-edit-form{margin-top:12px;border-top:1px solid var(--line);padding-top:12px}.access-chip{display:inline-flex;border:1px solid rgba(248,154,32,.35);background:rgba(248,154,32,.09);color:#ffd49a;border-radius:999px;padding:5px 9px;font-size:12px;font-weight:900}.form-stack small.muted{display:block;margin-top:3px}.register-panel .form-grid.compact{grid-template-columns:repeat(2,minmax(0,1fr));max-width:760px}.register-panel .form-grid.compact .full{grid-column:1/-1}\n@media (max-width:1100px){.permission-grid{grid-template-columns:1fr}.user-admin-head{flex-direction:column}.user-admin-head div:last-child{justify-content:flex-start}}\n@media (max-width:780px){.register-panel .form-grid.compact{grid-template-columns:1fr}.user-edit-form{grid-template-columns:1fr!important}}\n\n.login-back { margin: 10px 0 18px; text-align: center; }\n.login-back a { color: var(--muted); text-decoration: none; font-size: 0.9rem; }\n.login-back a:hover { color: var(--orange); }\n\n  </style>\n\n</head>\n<body>\n  {% if g.user %}\n  <aside class=\"sidebar\">\n    <a class=\"brand\" href=\"{{ url_for('index') }}\">\n      <img src=\"{{ url_for('static', filename='img/logo_mark_dark.png') }}\" alt=\"Atacarejo Insights\">\n      <span><strong>Atacarejo</strong><small>Insights Portal</small></span>\n    </a>\n    <nav>\n      {% if g.user.role in ['admin', 'consultant'] %}\n      <a href=\"{{ url_for('admin_dashboard') }}\">Visão geral</a>\n      <a href=\"{{ url_for('admin_leads') }}\">Leads do site</a>\n      <a href=\"{{ url_for('admin_approvals') }}\">Aprovações</a>\n      <a href=\"{{ url_for('clients') }}\">Clientes</a>\n      <a href=\"{{ url_for('users') }}\">Usuários e acessos</a>\n      {% else %}\n      <a href=\"{{ url_for('client_dashboard') }}\">Meu projeto</a>\n      <a href=\"{{ url_for('company_detail', company_id=g.user.company_id) }}\">Minha empresa</a>\n      <a href=\"{{ url_for('client_company_edit') }}\">Alterações cadastrais</a>\n      {% if g.user.role == 'client_admin' %}<a href=\"{{ url_for('client_users') }}\">Usuários do cliente</a>{% endif %}\n      <a href=\"{{ url_for('diagnostic', company_id=g.user.company_id) }}\">Diagnóstico</a>\n      {% endif %}\n    </nav>\n    <div class=\"sidebar-footer\">\n      <small>{{ g.user.name }}</small>\n      <small>{{ role_labels.get(g.user.role, g.user.role) }}</small>\n      <a class=\"logout\" href=\"{{ url_for('logout') }}\">Sair</a>\n    </div>\n  </aside>\n  {% endif %}\n\n  <main class=\"main {% if not g.user %}main-public{% endif %}\">\n    {% with messages = get_flashed_messages(with_categories=true) %}\n      {% if messages %}\n        <div class=\"flash-area\">\n        {% for category, message in messages %}\n          <div class=\"flash {{ category }}\">{{ message }}</div>\n        {% endfor %}\n        </div>\n      {% endif %}\n    {% endwith %}\n    {% block content %}{% endblock %}\n    <footer class=\"app-footer\">© {{ current_year }} Atacarejo Insights · Planejamento, dados e gestão consultiva com confidencialidade por cliente</footer>\n  </main>\n  <script src=\"{{ url_for('static', filename='js/app.js') }}?v=16\"></script>\n</body>\n</html>\n",
  "login.html": "{% extends 'base.html' %}\n{% block title %}Login · Atacarejo Insights Portal{% endblock %}\n{% block content %}\n<section class=\"login-shell\">\n  <div class=\"login-card\">\n    <img class=\"login-logo\" src=\"{{ url_for('static', filename='img/logo.png') }}\" alt=\"Atacarejo Insights\">\n    <h1>Portal de Gestão Consultiva</h1>\n    <p>Diagnóstico empresarial, estruturação de projetos e acompanhamento seguro por cliente.</p>\n    <div class=\"login-back\"><a href=\"{{ url_for('index') }}\">← Voltar para a página institucional</a></div>\n    <form method=\"post\" class=\"form-stack\">\n      <label>E-mail\n        <input type=\"email\" name=\"email\" placeholder=\"seu@email.com\" required autofocus>\n      </label>\n      <label>Senha\n        <input type=\"password\" name=\"password\" placeholder=\"Digite sua senha\" required>\n      </label>\n      <button class=\"btn-primary\" type=\"submit\">Entrar</button>\n    </form>\n    <div class=\"demo-box\">\n      <strong>Acessos de demonstração</strong>\n      <span>Admin: admin@atacarejoinsights.com · senha: admin123</span>\n      <span>Cliente: cliente@demo.com · senha: cliente123</span>\n    </div>\n  </div>\n</section>\n{% endblock %}\n",
  "admin_dashboard.html": "{% extends 'base.html' %}\n{% block title %}Visão geral · Atacarejo Insights{% endblock %}\n{% block content %}\n<header class=\"page-header\">\n  <div>\n    <p class=\"eyebrow\">Administração</p>\n    <h1>Visão geral da Atacarejo Insights</h1>\n    <p>Controle central de clientes, projetos, produtividade, contratos e diagnóstico.</p>\n  </div>\n  <a class=\"btn-primary\" href=\"{{ url_for('client_new') }}\">Novo cliente</a>\n</header>\n\n<section class=\"metric-grid\">\n  <article class=\"metric-card\"><span>Clientes cadastrados</span><strong>{{ metrics.clients }}</strong></article>\n  <article class=\"metric-card\"><span>Projetos ativos</span><strong>{{ metrics.active_projects }}</strong></article>\n  <article class=\"metric-card\"><span>Tarefas abertas</span><strong>{{ metrics.open_tasks }}</strong></article>\n  <article class=\"metric-card\"><span>Receita vigente</span><strong>R$ {{ '%.2f'|format(metrics.revenue or 0) }}</strong></article>\n  <article class=\"metric-card accent\"><span>Maturidade média</span><strong>{{ '%.1f'|format(metrics.avg_maturity or 0) }}/5</strong></article>\n  <article class=\"metric-card\"><span>Leads em aberto</span><strong>{{ metrics.pending_leads }}</strong><small><a class=\"link\" href=\"{{ url_for('admin_leads') }}\">Gerenciar leads</a></small></article>\n  <article class=\"metric-card\"><span>Aprovações pendentes</span><strong>{{ metrics.pending_approvals }}</strong><small><a class=\"link\" href=\"{{ url_for('admin_approvals') }}\">Revisar alterações</a></small></article>\n</section>\n\n<section class=\"grid-2\">\n  <div class=\"panel\">\n    <div class=\"panel-title\"><h2>Clientes e maturidade</h2><a href=\"{{ url_for('clients') }}\">Ver todos</a></div>\n    <div class=\"table-wrap\">\n      <table>\n        <thead><tr><th>Cliente</th><th>Status</th><th>Projetos</th><th>Maturidade</th><th></th></tr></thead>\n        <tbody>\n          {% for c in companies %}\n          <tr>\n            <td><strong>{{ c.name }}</strong><br><small>{{ c.segment or '-' }} · {{ c.city or '-' }}/{{ c.state or '-' }}</small></td>\n            <td><span class=\"status-pill\">{{ c.status }}</span></td>\n            <td>{{ c.projects_count }}</td>\n            <td>{{ '%.1f'|format(c.maturity or 0) }}/5</td>\n            <td><a class=\"link\" href=\"{{ url_for('company_detail', company_id=c.id) }}\">Abrir</a></td>\n          </tr>\n          {% else %}\n          <tr><td colspan=\"5\">Nenhum cliente cadastrado.</td></tr>\n          {% endfor %}\n        </tbody>\n      </table>\n    </div>\n  </div>\n\n  <div class=\"panel\">\n    <div class=\"panel-title\"><h2>Pipeline dos projetos</h2></div>\n    {% for p in pipeline %}\n      <div class=\"pipeline-row\">\n        <div><strong>{{ p.phase }}</strong><small>{{ p.total }} projeto(s)</small></div>\n        <div class=\"progress\"><span style=\"width: {{ p.avg_progress or 0 }}%\"></span></div>\n        <small>{{ p.avg_progress or 0 }}%</small>\n      </div>\n    {% else %}\n      <p class=\"muted\">Sem projetos para exibir.</p>\n    {% endfor %}\n  </div>\n</section>\n\n<section class=\"panel\">\n  <div class=\"panel-title\"><h2>Riscos de prazo</h2></div>\n  <div class=\"cards-row\">\n    {% for t in overdue %}\n    <article class=\"mini-card danger\">\n      <small>{{ t.company_name }}</small>\n      <strong>{{ t.title }}</strong>\n      <span>{{ t.project_name }}</span>\n      <em>Vencimento: {{ t.due_date }}</em>\n    </article>\n    {% else %}\n    <p class=\"muted\">Nenhuma tarefa vencida.</p>\n    {% endfor %}\n  </div>\n</section>\n{% endblock %}\n",
  "client_dashboard.html": "{% extends 'base.html' %}\n{% block title %}Meu projeto · Atacarejo Insights{% endblock %}\n{% block content %}\n<header class=\"page-header\">\n  <div>\n    <p class=\"eyebrow\">Ambiente do cliente</p>\n    <h1>{{ company.name }}</h1>\n    <p>Visualização restrita às informações da sua empresa, com diagnóstico, imersões, etapas do projeto e pendências.</p>\n  </div>\n  <div class=\"header-actions\"><a class=\"btn-outline\" href=\"{{ url_for('client_company_edit') }}\">Atualizar cadastro</a><a class=\"btn-outline\" href=\"{{ url_for('company_report', company_id=company.id) }}\">Relatório</a></div>\n</header>\n\n\n{% if pending_changes %}\n<section class=\"panel approval-summary\">\n  <div class=\"panel-title\"><h2>Alterações aguardando aprovação</h2><a href=\"{{ url_for('client_company_edit') }}\">Ver solicitações</a></div>\n  <div class=\"cards-row\">\n    {% for cr in pending_changes %}\n    <article class=\"mini-card\">\n      <small>{{ cr.created_at }} · {{ cr.user_name or 'Usuário' }}</small>\n      <strong>{{ cr.field_name }}</strong>\n      <span class=\"status-pill warning\">Pendente</span>\n    </article>\n    {% endfor %}\n  </div>\n</section>\n{% endif %}\n\n<section class=\"grid-2\">\n  <div class=\"panel hero-panel\">\n    <div class=\"panel-title\"><h2>Status dos projetos</h2></div>\n    {% for p in projects %}\n      <article class=\"project-card project-card-wide\">\n        <div>\n          <strong>{{ p.name }}</strong>\n          <small>{{ p.phase }} · {{ p.status }} · {{ p.start_date or '-' }} até {{ p.end_date or '-' }}</small>\n        </div>\n        <div class=\"progress big\"><span style=\"width: {{ p.progress }}%\"></span></div>\n        <div class=\"card-actions\"><span class=\"status-pill\">{{ p.progress }}%</span><a class=\"link\" href=\"{{ url_for('project_detail', project_id=p.id) }}\">Acompanhar jornada</a></div>\n      </article>\n    {% else %}\n      <p class=\"muted\">Nenhum projeto ativo.</p>\n    {% endfor %}\n  </div>\n\n  <div class=\"panel\">\n    <div class=\"panel-title\"><h2>Maturidade do diagnóstico</h2><a href=\"{{ url_for('diagnostic', company_id=company.id) }}\">Atualizar</a></div>\n    {% for m in maturity %}\n      <div class=\"maturity-row\">\n        <span>{{ m.name }}</span>\n        <div class=\"scorebar\"><i style=\"width: {{ (m.score or 0) * 20 }}%\"></i></div>\n        <strong>{{ m.score or 0 }}/5</strong>\n      </div>\n    {% endfor %}\n  </div>\n</section>\n\n<section class=\"panel\">\n  <div class=\"panel-title\">\n    <div>\n      <h2>Jornada do projeto</h2>\n      <p class=\"muted\">Etapas liberadas pela Atacarejo Insights para acompanhamento do cliente.</p>\n    </div>\n  </div>\n  <div class=\"journey-horizontal\" aria-label=\"Jornada horizontal do projeto\">\n    {% for s in project_stages %}\n      <a class=\"journey-step {{ 'done' if s.status == 'Concluída' else 'active' if s.status == 'Em andamento' else 'pending' }}\"\n         href=\"{{ url_for('stage_detail', stage_id=s.id) }}\"\n         title=\"{{ s.project_name }} · {{ s.status }}\">\n        <span class=\"step-number\">{{ s.sort_order }}</span>\n        <strong>{{ s.title }}</strong>\n      </a>\n    {% else %}\n      <p class=\"muted\">A jornada do projeto ainda não foi publicada para o cliente.</p>\n    {% endfor %}\n  </div>\n  <p class=\"journey-hint\">Clique em uma etapa para abrir as informações, datas, descrição, registros e plano de ação vinculado ao projeto.</p>\n</section>\n\n<section class=\"panel\">\n  <div class=\"panel-title\">\n    <div>\n      <h2>Imersões e questionários aplicados</h2>\n      <p class=\"muted\">Aqui ficam as respostas por usuário/área: operação, compras, vendas, marketing, diretoria e demais gestores.</p>\n    </div>\n  </div>\n  <div class=\"questionnaire-grid\">\n    {% for q in questionnaires %}\n      <article class=\"questionnaire-card\">\n        <div class=\"q-head\">\n          <span class=\"q-area\">{{ q.context_area or 'Diagnóstico' }}</span>\n          <span class=\"status-pill\">{{ q.status }}</span>\n        </div>\n        <h3>{{ q.title }}</h3>\n        <p>{{ q.description or '' }}</p>\n        <div class=\"q-meta\">\n          <span>Perfil-alvo: <strong>{{ q.target_role or '-' }}</strong></span>\n          <span>Respondentes: <strong>{{ q.respondent_count or 0 }}</strong></span>\n          <span>Respostas: <strong>{{ q.answer_count or 0 }}</strong></span>\n        </div>\n        <a class=\"btn-outline full-btn\" href=\"{{ url_for('questionnaire_detail', questionnaire_id=q.id) }}\">Ver respostas e contribuir</a>\n      </article>\n    {% else %}\n      <p class=\"muted\">Nenhum questionário liberado ainda.</p>\n    {% endfor %}\n  </div>\n</section>\n\n<section class=\"grid-2\">\n  <div class=\"panel\">\n    <div class=\"panel-title\"><h2>Pendências e tarefas</h2></div>\n    <div class=\"task-list\">\n      {% for t in tasks %}\n      <div class=\"task-item\">\n        <div>\n          <strong>{{ t.title }}</strong>\n          <small>{{ t.project_name }} · Responsável: {{ t.owner or '-' }} · Equipe: {{ t.responsible_team or '-' }}</small>\n          <small>Início: {{ t.start_date or '-' }} · Prazo: {{ t.due_date or '-' }} · Conclusão: {{ t.completed_at or '-' }}</small>\n        </div>\n        <span class=\"status-pill {{ task_condition_class(t) }}\">{{ task_condition(t) }}</span>\n      </div>\n      {% else %}<p class=\"muted\">Sem tarefas cadastradas.</p>{% endfor %}\n    </div>\n  </div>\n  <div class=\"panel\">\n    <div class=\"panel-title\"><h2>Dados solicitados</h2></div>\n    {% for f in files %}\n      <div class=\"file-row\"><div><strong>{{ f.title }}</strong><small>{{ f.file_type or '-' }} · prazo {{ f.due_date or '-' }}</small></div><span class=\"status-pill\">{{ f.status }}</span></div>\n    {% else %}<p class=\"muted\">Nenhum documento solicitado.</p>{% endfor %}\n  </div>\n</section>\n{% endblock %}\n",
  "clients.html": "{% extends 'base.html' %}\n{% block title %}Clientes · Atacarejo Insights{% endblock %}\n{% block content %}\n<header class=\"page-header\">\n  <div>\n    <p class=\"eyebrow\">Carteira</p>\n    <h1>Clientes</h1>\n    <p>Cadastro e acompanhamento individualizado por empresa.</p>\n  </div>\n  <a class=\"btn-primary\" href=\"{{ url_for('client_new') }}\">Cadastrar cliente</a>\n</header>\n<section class=\"panel\">\n  <div class=\"table-wrap\">\n    <table>\n      <thead><tr><th>Empresa</th><th>Segmento</th><th>Cidade</th><th>Lojas</th><th>Status</th><th></th></tr></thead>\n      <tbody>\n      {% for c in companies %}\n        <tr>\n          <td><strong>{{ c.name }}</strong><br><small>{{ c.cnpj or 'CNPJ não informado' }}</small></td>\n          <td>{{ c.segment or '-' }}</td>\n          <td>{{ c.city or '-' }}/{{ c.state or '-' }}</td>\n          <td>{{ c.stores or 0 }}</td>\n          <td><span class=\"status-pill\">{{ c.status }}</span></td>\n          <td><a class=\"link\" href=\"{{ url_for('company_detail', company_id=c.id) }}\">Abrir</a></td>\n        </tr>\n      {% else %}\n        <tr><td colspan=\"6\">Nenhum cliente cadastrado.</td></tr>\n      {% endfor %}\n      </tbody>\n    </table>\n  </div>\n</section>\n{% endblock %}\n",
  "client_form.html": "{% extends 'base.html' %}\n{% block title %}Novo cliente · Atacarejo Insights{% endblock %}\n{% block content %}\n<header class=\"page-header\">\n  <div>\n    <p class=\"eyebrow\">Cadastro</p>\n    <h1>Novo cliente</h1>\n    <p>Registre a empresa para iniciar diagnóstico, contrato e projeto.</p>\n  </div>\n</header>\n<section class=\"panel\">\n  <form method=\"post\" class=\"form-grid\">\n    <label>Nome da empresa<input name=\"name\" required></label>\n    <label>CNPJ<input name=\"cnpj\"></label>\n    <label>Segmento<input name=\"segment\" placeholder=\"Supermercado, atacarejo, distribuidor...\"></label>\n    <label>Cidade<input name=\"city\"></label>\n    <label>Estado<input name=\"state\" maxlength=\"2\" placeholder=\"PE\"></label>\n    <label>Número de lojas<input name=\"stores\" type=\"number\" min=\"0\" value=\"0\"></label>\n    <label>Faturamento mensal estimado<input name=\"monthly_revenue\" type=\"number\" step=\"0.01\" min=\"0\" value=\"0\"></label>\n    <label>Responsável<input name=\"contact_name\"></label>\n    <label>E-mail do responsável<input name=\"contact_email\" type=\"email\"></label>\n    <label>Status\n      <select name=\"status\">\n        <option>Prospecção</option>\n        <option selected>Diagnóstico</option>\n        <option>Execução</option>\n        <option>Finalização</option>\n        <option>Encerrado</option>\n      </select>\n    </label>\n    <div class=\"form-actions\"><button class=\"btn-primary\" type=\"submit\">Salvar cliente</button></div>\n  </form>\n</section>\n{% endblock %}\n",
  "company_detail.html": "{% extends 'base.html' %}\n{% block title %}{{ company.name }} · Atacarejo Insights{% endblock %}\n{% block content %}\n<header class=\"page-header\">\n  <div>\n    <p class=\"eyebrow\">Cliente</p>\n    <h1>{{ company.name }}</h1>\n    <p>{{ company.segment or 'Segmento não informado' }} · {{ company.city or '-' }}/{{ company.state or '-' }} · {{ company.stores or 0 }} loja(s)</p>\n  </div>\n  <div class=\"header-actions\">\n    <a class=\"btn-outline\" href=\"{{ url_for('company_report', company_id=company.id) }}\">Relatório</a>\n    <a class=\"btn-primary\" href=\"{{ url_for('diagnostic', company_id=company.id) }}\">Diagnóstico</a>\n  </div>\n</header>\n\n<section class=\"metric-grid small\">\n  <article class=\"metric-card\"><span>Status</span><strong>{{ company.status }}</strong></article>\n  <article class=\"metric-card\"><span>Faturamento mensal estimado</span><strong>R$ {{ '%.2f'|format(company.monthly_revenue or 0) }}</strong></article>\n  <article class=\"metric-card\"><span>Contato</span><strong>{{ company.contact_name or '-' }}</strong><small>{{ company.contact_email or '' }}</small></article>\n</section>\n\n{% if pending_changes and g.user.role in ['admin', 'consultant'] %}\n<section class=\"panel approval-summary\">\n  <div class=\"panel-title\"><h2>Alterações pendentes deste cliente</h2><a href=\"{{ url_for('admin_approvals') }}\">Revisar aprovações</a></div>\n  <div class=\"cards-row\">\n    {% for cr in pending_changes %}\n      <article class=\"mini-card\"><small>{{ cr.created_at }} · {{ cr.user_name or '-' }}</small><strong>{{ cr.field_name }}</strong><span class=\"status-pill warning\">Pendente</span></article>\n    {% endfor %}\n  </div>\n</section>\n{% endif %}\n\n<section class=\"grid-2\">\n  <div class=\"panel\">\n    <div class=\"panel-title\">\n      <h2>Projetos</h2>\n      {% if g.user.role in ['admin', 'consultant'] %}<a href=\"{{ url_for('project_new', company_id=company.id) }}\">Novo projeto</a>{% endif %}\n    </div>\n    {% for p in projects %}\n      <article class=\"project-card\">\n        <div><strong>{{ p.name }}</strong><small>{{ p.phase }} · {{ p.status }}</small></div>\n        <div class=\"progress\"><span style=\"width: {{ p.progress }}%\"></span></div>\n        <a class=\"link\" href=\"{{ url_for('project_detail', project_id=p.id) }}\">Abrir</a>\n      </article>\n    {% else %}<p class=\"muted\">Nenhum projeto cadastrado.</p>{% endfor %}\n  </div>\n\n  <div class=\"panel\">\n    <div class=\"panel-title\"><h2>Matriz de maturidade</h2></div>\n    {% for m in maturity %}\n      <div class=\"maturity-row\">\n        <span>{{ m.name }}</span>\n        <div class=\"scorebar\"><i style=\"width: {{ (m.score or 0) * 20 }}%\"></i></div>\n        <strong>{{ m.score or 0 }}/5</strong>\n      </div>\n    {% endfor %}\n  </div>\n</section>\n\n<section class=\"panel\">\n  <div class=\"panel-title\">\n    <div>\n      <h2>Áreas mapeadas para diagnóstico e imersão</h2>\n      <p class=\"muted\">Levantamento base de áreas normalmente encontradas em empresas de supermercado, atacarejo, distribuição e varejo alimentar. Você pode adicionar novas áreas quando o cliente tiver uma estrutura específica.</p>\n    </div>\n  </div>\n  <div class=\"tag-cloud\">\n    {% for area in area_options %}\n      <span class=\"area-tag\" title=\"{{ area.description or '' }}\">{{ area.name }}</span>\n    {% endfor %}\n  </div>\n  {% if g.user.role in ['admin', 'consultant'] %}\n  <details class=\"admin-create\">\n    <summary>Adicionar área não mapeada</summary>\n    <form method=\"post\" action=\"{{ url_for('area_new') }}\" class=\"form-grid compact\">\n      <input type=\"hidden\" name=\"company_id\" value=\"{{ company.id }}\">\n      <label>Nome da área<input name=\"name\" placeholder=\"Ex.: Auditoria interna, Patrimônio, Segurança patrimonial...\" required></label>\n      <label class=\"full\">Descrição da área<textarea name=\"description\" rows=\"3\" placeholder=\"Explique o escopo desta área dentro do cliente.\"></textarea></label>\n      <div class=\"form-actions\"><button class=\"btn-outline\" type=\"submit\">Adicionar área</button></div>\n    </form>\n  </details>\n  {% endif %}\n</section>\n\n<section class=\"panel\">\n  <div class=\"panel-title\">\n    <div>\n      <h2>Imersões e questionários por área</h2>\n      <p class=\"muted\">Controle dos questionários aplicados aos gestores do cliente e das respostas registradas por usuário.</p>\n    </div>\n  </div>\n  <div class=\"questionnaire-grid\">\n    {% for q in questionnaires %}\n      <article class=\"questionnaire-card\">\n        <div class=\"q-head\"><span class=\"q-area\">{{ q.context_area or 'Diagnóstico' }}</span><span class=\"status-pill\">{{ q.status }}</span></div>\n        <h3>{{ q.title }}</h3>\n        <p>{{ q.description or '' }}</p>\n        <div class=\"q-meta\"><span>Perfil: <strong>{{ q.target_role or '-' }}</strong></span><span>Respondentes: <strong>{{ q.respondent_count or 0 }}</strong></span><span>Respostas: <strong>{{ q.answer_count or 0 }}</strong></span></div>\n        <a class=\"btn-outline full-btn\" href=\"{{ url_for('questionnaire_detail', questionnaire_id=q.id) }}\">Abrir questionário</a>\n      </article>\n    {% else %}<p class=\"muted\">Nenhum questionário cadastrado.</p>{% endfor %}\n  </div>\n  {% if g.user.role in ['admin', 'consultant'] %}\n  <details class=\"admin-create\">\n    <summary>Criar novo questionário de imersão</summary>\n    <form method=\"post\" action=\"{{ url_for('questionnaire_new', company_id=company.id) }}\" class=\"form-grid compact\">\n      <label>Título<input name=\"title\" placeholder=\"Ex.: Imersão Financeira\" required></label>\n      <label>Área mapeada\n        <select name=\"context_area\">\n          <option value=\"\">Selecionar área previamente mapeada</option>\n          {% for area in area_options %}\n          <option value=\"{{ area.name }}\">{{ area.name }}</option>\n          {% endfor %}\n        </select>\n      </label>\n      <label>Nova área, se não estiver na lista<input name=\"custom_area\" placeholder=\"Ex.: Auditoria interna, Patrimônio, Segurança...\"></label>\n      <label>Perfil-alvo<input name=\"target_role\" placeholder=\"Gerente financeiro, diretor, comprador...\"></label>\n      <label>Status<select name=\"status\"><option>Aberto</option><option selected>Em coleta</option><option>Em análise</option><option>Fechado</option></select></label>\n      <label>Visível ao cliente<select name=\"visible_to_client\"><option value=\"1\" selected>Sim</option><option value=\"0\">Não</option></select></label>\n      <label class=\"full\">Descrição<textarea name=\"description\" rows=\"3\"></textarea></label>\n      <label class=\"full\">Perguntas, uma por linha<textarea name=\"questions\" rows=\"6\" placeholder=\"Se você deixar em branco, o sistema usará um roteiro-base da área selecionada.&#10;Ex.: Quais são os principais gargalos da área?&#10;Quais indicadores são acompanhados?&#10;Quais oportunidades devem ser priorizadas?\"></textarea></label>\n      <p class=\"full muted\">Dica: ao selecionar uma área mapeada e deixar as perguntas em branco, o portal cria automaticamente perguntas-base para a imersão daquela área.</p>\n      <div class=\"form-actions\"><button class=\"btn-primary\" type=\"submit\">Criar questionário</button></div>\n    </form>\n  </details>\n  {% endif %}\n</section>\n\n<section class=\"grid-2\">\n  <div class=\"panel\">\n    <div class=\"panel-title\"><h2>Dados e documentos necessários</h2></div>\n    {% for f in files %}\n      <div class=\"file-row\"><div><strong>{{ f.title }}</strong><small>{{ f.file_type or '-' }} · {{ f.notes or '' }}</small></div><span class=\"status-pill\">{{ f.status }}</span></div>\n    {% else %}<p class=\"muted\">Sem documentos registrados.</p>{% endfor %}\n    {% if g.user.role != 'client_viewer' %}\n    <form method=\"post\" action=\"{{ url_for('file_new', company_id=company.id) }}\" class=\"inline-form\">\n      <input name=\"title\" placeholder=\"Novo dado/documento\" required>\n      <input name=\"file_type\" placeholder=\"Tipo\">\n      <input name=\"due_date\" type=\"date\">\n      <select name=\"status\"><option>Solicitado</option><option>Recebido</option><option>Em análise</option></select>\n      <button class=\"btn-outline\" type=\"submit\">Adicionar</button>\n    </form>\n    {% endif %}\n  </div>\n\n  <div class=\"panel\">\n    <div class=\"panel-title\"><h2>Usuários do cliente</h2></div>\n    {% for u in users %}\n      <div class=\"user-row\"><div><strong>{{ u.name }}</strong><small>{{ u.email }}</small></div><span class=\"status-pill\">{{ role_labels.get(u.role, u.role) }}</span></div>\n    {% else %}<p class=\"muted\">Sem usuários vinculados.</p>{% endfor %}\n  </div>\n</section>\n{% endblock %}\n",
  "project_form.html": "{% extends 'base.html' %}\n{% block title %}Novo projeto · Atacarejo Insights{% endblock %}\n{% block content %}\n<header class=\"page-header\"><div><p class=\"eyebrow\">{{ company.name }}</p><h1>Novo projeto</h1><p>Estruture o escopo inicial de acompanhamento.</p></div></header>\n<section class=\"panel\">\n  <form method=\"post\" class=\"form-grid\">\n    <label>Nome do projeto<input name=\"name\" required></label>\n    <label>Fase<select name=\"phase\"><option>Onboarding</option><option>Coleta de dados</option><option>Diagnóstico inicial</option><option>Plano de ação</option><option>Execução assistida</option><option>Monitoramento</option><option>Relatório final</option></select></label>\n    <label>Progresso (%)<input name=\"progress\" type=\"number\" min=\"0\" max=\"100\" value=\"0\"></label>\n    <label>Status<select name=\"status\"><option>Em andamento</option><option>Pausado</option><option>Finalizado</option></select></label>\n    <label>Início<input name=\"start_date\" type=\"date\"></label>\n    <label>Término previsto<input name=\"end_date\" type=\"date\"></label>\n    <label class=\"full\">Objetivo<textarea name=\"objective\" rows=\"5\"></textarea></label>\n    <div class=\"form-actions\"><button class=\"btn-primary\" type=\"submit\">Criar projeto</button></div>\n  </form>\n</section>\n{% endblock %}\n",
  "project_detail.html": "{% extends 'base.html' %}\n{% block title %}{{ project.name }} · Atacarejo Insights{% endblock %}\n{% block content %}\n<header class=\"page-header\">\n  <div>\n    <p class=\"eyebrow\">{{ project.company_name }}</p>\n    <h1>{{ project.name }}</h1>\n    <p>{{ project.objective or 'Sem objetivo informado.' }}</p>\n  </div>\n  <a class=\"btn-outline\" href=\"{{ url_for('company_detail', company_id=project.company_id) }}\">Voltar ao cliente</a>\n</header>\n\n<section class=\"metric-grid small\">\n  <article class=\"metric-card\"><span>Fase</span><strong>{{ project.phase }}</strong></article>\n  <article class=\"metric-card\"><span>Status</span><strong>{{ project.status }}</strong></article>\n  <article class=\"metric-card accent\"><span>Progresso</span><strong>{{ project.progress }}%</strong><div class=\"progress\"><span style=\"width: {{ project.progress }}%\"></span></div></article>\n</section>\n\n<section class=\"panel\">\n  <div class=\"panel-title\">\n    <div>\n      <h2>Jornada do projeto visível ao cliente</h2>\n      <p class=\"muted\">Controle em qual etapa o projeto está, o que já foi concluído e quais são os próximos passos até o encerramento.</p>\n    </div>\n  </div>\n  <div class=\"journey-horizontal admin-journey\" aria-label=\"Jornada horizontal do projeto\">\n    {% for s in stages %}\n      <a class=\"journey-step {{ 'done' if s.status == 'Concluída' else 'active' if s.status == 'Em andamento' else 'pending' }}\"\n         href=\"{{ url_for('stage_detail', stage_id=s.id) }}\"\n         title=\"{{ s.status }}\">\n        <span class=\"step-number\">{{ s.sort_order }}</span>\n        <strong>{{ s.title }}</strong>\n      </a>\n    {% else %}\n      <p class=\"muted\">Nenhuma etapa cadastrada ainda.</p>\n    {% endfor %}\n  </div>\n  <p class=\"journey-hint\">Clique sobre uma etapa para acessar as informações específicas dela. O cliente verá a mesma jornada horizontal, respeitando as etapas marcadas como visíveis.</p>\n\n  {% if g.user.role in ['admin', 'consultant'] %}\n  <details class=\"admin-create stage-admin-editor\">\n    <summary>Editar etapas da jornada</summary>\n    <div class=\"stage-editor-list\">\n    {% for s in stages %}\n      <article class=\"timeline-content\">\n        <form method=\"post\" action=\"{{ url_for('stage_update', stage_id=s.id) }}\" class=\"stage-edit-form\">\n          <div class=\"stage-edit-grid\">\n            <label>Ordem<input name=\"sort_order\" type=\"number\" value=\"{{ s.sort_order }}\"></label>\n            <label>Título<input name=\"title\" value=\"{{ s.title }}\" required></label>\n            <label>Status<select name=\"status\">{% for st in ['Pendente', 'Em andamento', 'Concluída'] %}<option value=\"{{ st }}\" {{ 'selected' if s.status == st else '' }}>{{ st }}</option>{% endfor %}</select></label>\n            <label>Início<input name=\"start_date\" type=\"date\" value=\"{{ s.start_date or '' }}\"></label>\n            <label>Término<input name=\"end_date\" type=\"date\" value=\"{{ s.end_date or '' }}\"></label>\n            <label>Visível<select name=\"visible_to_client\"><option value=\"1\" {{ 'selected' if s.visible_to_client == 1 else '' }}>Sim</option><option value=\"0\" {{ 'selected' if s.visible_to_client != 1 else '' }}>Não</option></select></label>\n            <label class=\"full\">Descrição/informações da etapa<textarea name=\"description\" rows=\"3\">{{ s.description or '' }}</textarea></label>\n          </div>\n          <button class=\"btn-outline\" type=\"submit\">Salvar etapa</button>\n        </form>\n      </article>\n    {% endfor %}\n    </div>\n  </details>\n  {% endif %}\n  {% if g.user.role in ['admin', 'consultant'] %}\n  <details class=\"admin-create\">\n    <summary>Adicionar nova etapa ao cronograma</summary>\n    <form method=\"post\" action=\"{{ url_for('stage_new', project_id=project.id) }}\" class=\"form-grid compact\">\n      <label>Ordem<input name=\"sort_order\" type=\"number\" value=\"{{ (stages|length) + 1 }}\"></label>\n      <label>Título<input name=\"title\" required></label>\n      <label>Status<select name=\"status\"><option>Pendente</option><option>Em andamento</option><option>Concluída</option></select></label>\n      <label>Início<input name=\"start_date\" type=\"date\"></label>\n      <label>Término<input name=\"end_date\" type=\"date\"></label>\n      <label>Visível ao cliente<select name=\"visible_to_client\"><option value=\"1\" selected>Sim</option><option value=\"0\">Não</option></select></label>\n      <label class=\"full\">Descrição<textarea name=\"description\" rows=\"3\"></textarea></label>\n      <div class=\"form-actions\"><button class=\"btn-primary\" type=\"submit\">Adicionar etapa</button></div>\n    </form>\n  </details>\n  {% endif %}\n</section>\n\n{% if g.user.role in ['admin', 'consultant'] %}\n<section class=\"panel collapsible\">\n  <details>\n    <summary>Editar dados do projeto</summary>\n    <form method=\"post\" class=\"form-grid compact\">\n      <label>Nome<input name=\"name\" value=\"{{ project.name }}\" required></label>\n      <label>Fase<input name=\"phase\" value=\"{{ project.phase }}\"></label>\n      <label>Progresso (%)<input name=\"progress\" type=\"number\" min=\"0\" max=\"100\" value=\"{{ project.progress }}\"></label>\n      <label>Status<select name=\"status\"><option {{ 'selected' if project.status == 'Em andamento' else '' }}>Em andamento</option><option {{ 'selected' if project.status == 'Pausado' else '' }}>Pausado</option><option {{ 'selected' if project.status == 'Finalizado' else '' }}>Finalizado</option></select></label>\n      <label>Início<input name=\"start_date\" type=\"date\" value=\"{{ project.start_date }}\"></label>\n      <label>Término<input name=\"end_date\" type=\"date\" value=\"{{ project.end_date }}\"></label>\n      <label class=\"full\">Objetivo<textarea name=\"objective\" rows=\"4\">{{ project.objective or '' }}</textarea></label>\n      <div class=\"form-actions\"><button class=\"btn-primary\" type=\"submit\">Salvar alterações</button></div>\n    </form>\n  </details>\n</section>\n{% endif %}\n\n<section class=\"grid-2\">\n  <div class=\"panel\">\n    <div class=\"panel-title\">\n      <div>\n        <h2>Plano de ação e tarefas</h2>\n        <p class=\"muted\">Controle com responsável, equipe, início, prazo, conclusão e classificação automática de atrasos.</p>\n      </div>\n    </div>\n    <div class=\"task-list task-list-detailed\">\n      {% for t in tasks %}\n      <article class=\"task-item task-detailed\">\n        <div>\n          <strong>{{ t.title }}</strong>\n          <small>{{ t.description or '' }}</small>\n          <small>Responsável: {{ t.owner or '-' }} · Equipe: {{ t.responsible_team or '-' }} · Prioridade: {{ t.priority }}</small>\n          <small>Início: {{ t.start_date or '-' }} · Prazo atual: {{ t.due_date or '-' }} · Prazo original: {{ t.original_due_date or '-' }} · Conclusão: {{ t.completed_at or '-' }}</small>\n          {% if t.extension_reason %}<small>Motivo/observação: {{ t.extension_reason }}</small>{% endif %}\n        </div>\n        <div class=\"task-side\">\n          <span class=\"status-pill {{ task_condition_class(t) }}\">{{ task_condition(t) }}</span>\n          {% if g.user.role != 'client_viewer' %}\n          <form method=\"post\" action=\"{{ url_for('task_status', task_id=t.id) }}\" class=\"task-status-form\">\n            <select name=\"status\">\n              {% for s in ['Pendente', 'Em andamento', 'Prorrogada', 'Cancelada', 'Concluída'] %}\n              <option value=\"{{ s }}\" {{ 'selected' if t.status == s else '' }}>{{ s }}</option>\n              {% endfor %}\n            </select>\n            <input name=\"due_date\" type=\"date\" value=\"{{ t.due_date or '' }}\" title=\"Novo prazo, se houver prorrogação\">\n            <input name=\"extension_reason\" placeholder=\"Motivo/observação\">\n            <button class=\"btn-outline\" type=\"submit\">Atualizar</button>\n          </form>\n          {% endif %}\n          {% if g.user.role in ['admin', 'consultant'] %}\n          <details class=\"task-edit-details\">\n            <summary>Editar tarefa</summary>\n            <form method=\"post\" action=\"{{ url_for('task_update', task_id=t.id) }}\" class=\"form-stack compact-stack\">\n              <label>Título<input name=\"title\" value=\"{{ t.title }}\" required></label>\n              <label>Descrição<textarea name=\"description\" rows=\"2\">{{ t.description or '' }}</textarea></label>\n              <label>Responsável nominal<input name=\"owner\" value=\"{{ t.owner or '' }}\"></label>\n              <label>Equipe responsável<select name=\"responsible_team\"><option {{ 'selected' if t.responsible_team == 'Atacarejo Insights' else '' }}>Atacarejo Insights</option><option {{ 'selected' if t.responsible_team == 'Cliente' else '' }}>Cliente</option><option {{ 'selected' if t.responsible_team == 'Compartilhada' else '' }}>Compartilhada</option></select></label>\n              <label>Início<input name=\"start_date\" type=\"date\" value=\"{{ t.start_date or '' }}\"></label>\n              <label>Prazo<input name=\"due_date\" type=\"date\" value=\"{{ t.due_date or '' }}\"></label>\n              <label>Conclusão<input name=\"completed_at\" type=\"date\" value=\"{{ t.completed_at or '' }}\"></label>\n              <label>Status<select name=\"status\">{% for s in ['Pendente', 'Em andamento', 'Prorrogada', 'Cancelada', 'Concluída'] %}<option value=\"{{ s }}\" {{ 'selected' if t.status == s else '' }}>{{ s }}</option>{% endfor %}</select></label>\n              <label>Prioridade<select name=\"priority\"><option {{ 'selected' if t.priority == 'Baixa' else '' }}>Baixa</option><option {{ 'selected' if t.priority == 'Média' else '' }}>Média</option><option {{ 'selected' if t.priority == 'Alta' else '' }}>Alta</option></select></label>\n              <label>Motivo/observação<textarea name=\"extension_reason\" rows=\"2\">{{ t.extension_reason or '' }}</textarea></label>\n              <button class=\"btn-outline\" type=\"submit\">Salvar tarefa</button>\n            </form>\n          </details>\n          {% endif %}\n        </div>\n      </article>\n      {% else %}<p class=\"muted\">Nenhuma tarefa cadastrada.</p>{% endfor %}\n    </div>\n  </div>\n\n  <div class=\"panel\">\n    <div class=\"panel-title\"><h2>Adicionar tarefa</h2></div>\n    {% if g.user.role != 'client_viewer' %}\n    <form method=\"post\" action=\"{{ url_for('task_new', project_id=project.id) }}\" class=\"form-stack\">\n      <label>Título<input name=\"title\" required></label>\n      <label>Descrição<textarea name=\"description\" rows=\"3\"></textarea></label>\n      <label>Responsável nominal<input name=\"owner\" placeholder=\"Nome da pessoa responsável\"></label>\n      <label>Equipe responsável<select name=\"responsible_team\"><option>Atacarejo Insights</option><option>Cliente</option><option>Compartilhada</option></select></label>\n      <label>Data de início<input name=\"start_date\" type=\"date\"></label>\n      <label>Prazo<input name=\"due_date\" type=\"date\"></label>\n      <label>Status<select name=\"status\"><option>Pendente</option><option>Em andamento</option><option>Prorrogada</option><option>Cancelada</option><option>Concluída</option></select></label>\n      <label>Conclusão, se já finalizada<input name=\"completed_at\" type=\"date\"></label>\n      <label>Prioridade<select name=\"priority\"><option>Baixa</option><option selected>Média</option><option>Alta</option></select></label>\n      <label>Motivo/observação<textarea name=\"extension_reason\" rows=\"2\" placeholder=\"Use para prorrogação, cancelamento ou justificativa.\"></textarea></label>\n      <button class=\"btn-primary\" type=\"submit\">Adicionar tarefa</button>\n    </form>\n    {% else %}\n    <p class=\"muted\">Seu perfil permite apenas visualização.</p>\n    {% endif %}\n  </div>\n</section>\n\n<section class=\"grid-2\">\n  <div class=\"panel\">\n    <div class=\"panel-title\"><h2>Histórico e decisões</h2></div>\n    {% for n in notes %}\n      <div class=\"note\"><strong>{{ n.author_name or 'Sistema' }}</strong><small>{{ n.created_at }} · {{ n.visibility }}</small><p>{{ n.note }}</p></div>\n    {% else %}<p class=\"muted\">Sem comentários registrados.</p>{% endfor %}\n  </div>\n  <div class=\"panel\">\n    <div class=\"panel-title\"><h2>Novo comentário</h2></div>\n    {% if g.user.role != 'client_viewer' %}\n    <form method=\"post\" action=\"{{ url_for('note_new', project_id=project.id) }}\" class=\"form-stack\">\n      <label>Comentário<textarea name=\"note\" rows=\"5\" required></textarea></label>\n      {% if g.user.role in ['admin', 'consultant'] %}\n      <label>Visibilidade<select name=\"visibility\"><option>Cliente</option><option>Interna</option></select></label>\n      {% endif %}\n      <button class=\"btn-outline\" type=\"submit\">Registrar</button>\n    </form>\n    {% else %}<p class=\"muted\">Seu perfil permite apenas visualização.</p>{% endif %}\n  </div>\n</section>\n{% endblock %}\n",
  "diagnostic.html": "{% extends 'base.html' %}\n{% block title %}Diagnóstico · {{ company.name }}{% endblock %}\n{% block content %}\n<header class=\"page-header\">\n  <div>\n    <p class=\"eyebrow\">Diagnóstico empresarial</p>\n    <h1>{{ company.name }}</h1>\n    <p>Avalie a maturidade por área em escala de 1 a 5. O diagnóstico orienta o plano de ação da consultoria.</p>\n  </div>\n  <a class=\"btn-outline\" href=\"{{ url_for('company_detail', company_id=company.id) }}\">Voltar</a>\n</header>\n\n{% if g.user.role in ['admin', 'consultant'] %}\n<section class=\"panel collapsible\">\n  <details>\n    <summary>Adicionar nova área ao diagnóstico</summary>\n    <form method=\"post\" action=\"{{ url_for('area_new') }}\" class=\"form-grid compact\">\n      <input type=\"hidden\" name=\"company_id\" value=\"{{ company.id }}\">\n      <label>Nome da área<input name=\"name\" placeholder=\"Ex.: Auditoria interna, Segurança patrimonial, Patrimônio...\" required></label>\n      <label class=\"full\">Descrição<textarea name=\"description\" rows=\"3\" placeholder=\"Descreva o escopo da área para orientar o diagnóstico.\"></textarea></label>\n      <div class=\"form-actions\"><button class=\"btn-outline\" type=\"submit\">Adicionar área</button></div>\n    </form>\n  </details>\n</section>\n{% endif %}\n\n<section class=\"panel\">\n  <form method=\"post\" class=\"diagnostic-form\">\n    {% for area in areas %}\n    {% set answer = answers.get(area.id) %}\n    <article class=\"diagnostic-card\">\n      <div>\n        <h2>{{ area.name }}</h2>\n        <p>{{ area.description }}</p>\n      </div>\n      <div class=\"score-select\">\n        <label>Nota</label>\n        <select name=\"score_{{ area.id }}\" {% if g.user.role == 'client_viewer' %}disabled{% endif %}>\n          {% for n in [1,2,3,4,5] %}\n          <option value=\"{{ n }}\" {{ 'selected' if answer and answer.score == n else '' }}>{{ n }} - {{ ['','Inicial','Básico','Estruturado','Avançado','Referência'][n] }}</option>\n          {% endfor %}\n        </select>\n      </div>\n      <label class=\"full\">Observações e evidências\n        <textarea name=\"comment_{{ area.id }}\" rows=\"3\" {% if g.user.role == 'client_viewer' %}disabled{% endif %}>{{ answer.comment if answer else '' }}</textarea>\n      </label>\n    </article>\n    {% endfor %}\n    {% if g.user.role != 'client_viewer' %}\n    <div class=\"form-actions sticky\"><button class=\"btn-primary\" type=\"submit\">Salvar diagnóstico</button></div>\n    {% endif %}\n  </form>\n</section>\n{% endblock %}\n",
  "users.html": "{% extends 'base.html' %}\n{% block title %}Usuários e acessos · Atacarejo Insights{% endblock %}\n{% block content %}\n<header class=\"page-header\"><div><p class=\"eyebrow\">Governança de acessos</p><h1>Usuários, perfis e permissões</h1><p>Organize perfis internos da Atacarejo Insights e perfis dos clientes, preparando o fluxo para analistas responsáveis por projetos, áreas e empresas específicas.</p></div></header>\n\n<section class=\"grid-2\">\n  <div class=\"panel\">\n    <div class=\"panel-title\"><h2>Novo usuário</h2><small>Escolha um perfil modelo para preencher o papel de acesso e o escopo operacional.</small></div>\n    <form method=\"post\" class=\"form-stack\">\n      <label>Nome<input name=\"name\" required></label>\n      <label>E-mail<input name=\"email\" type=\"email\" required></label>\n      <label>Senha inicial<input name=\"password\" type=\"password\" placeholder=\"Padrão: 123456\"></label>\n      <label>Perfil modelo\n        <select name=\"profile_model\" required>\n          <optgroup label=\"Perfis internos Atacarejo Insights\">\n            {% for key, p in internal_profile_templates.items() %}<option value=\"{{ key }}\">{{ p.label }}</option>{% endfor %}\n          </optgroup>\n          <optgroup label=\"Perfis do cliente\">\n            {% for key, p in client_profile_templates.items() %}<option value=\"{{ key }}\">{{ p.label }}</option>{% endfor %}\n          </optgroup>\n        </select>\n      </label>\n      <label>Papel técnico\n        <select name=\"role\" required>\n          <option value=\"admin\">Administrador</option>\n          <option value=\"consultant\">Consultor interno</option>\n          <option value=\"client_admin\">Cliente administrador</option>\n          <option value=\"client_collaborator\">Cliente colaborador</option>\n          <option value=\"client_viewer\">Cliente visualizador</option>\n        </select>\n      </label>\n      <label>Área/função principal<input name=\"department_area\" placeholder=\"Ex.: Supply Chain, Compras, Logística, Diretoria...\"></label>\n      <label>Escopo de acesso\n        <select name=\"access_scope\">\n          {% for key, label in access_levels.items() %}<option value=\"{{ key }}\">{{ label }}</option>{% endfor %}\n        </select>\n      </label>\n      <label>Empresa do cliente\n        <select name=\"company_id\">\n          <option value=\"\">Sem vínculo / usuário interno</option>\n          {% for c in companies %}<option value=\"{{ c.id }}\">{{ c.name }}</option>{% endfor %}\n        </select>\n      </label>\n      <label>Projetos atribuídos\n        <select name=\"project_ids\" multiple size=\"5\">\n          {% for p in projects %}<option value=\"{{ p.id }}\">{{ p.company_name }} · {{ p.name }}</option>{% endfor %}\n        </select>\n        <small class=\"muted\">Use Ctrl para selecionar mais de um projeto.</small>\n      </label>\n      <label>Observações de permissão<textarea name=\"permission_notes\" rows=\"3\" placeholder=\"Ex.: acesso temporário, escopo por área, restrições específicas...\"></textarea></label>\n      <button class=\"btn-primary\" type=\"submit\">Criar usuário</button>\n    </form>\n  </div>\n\n  <div class=\"panel\">\n    <div class=\"panel-title\"><h2>Perfis modelo</h2><small>Referência rápida de governança.</small></div>\n    <div class=\"permission-grid\">\n      <div>\n        <h3>Internos</h3>\n        {% for key, p in internal_profile_templates.items() %}\n        <article class=\"permission-card\"><strong>{{ p.label }}</strong><span>{{ role_labels.get(p.role, p.role) }}</span><p>{{ p.scope }}</p></article>\n        {% endfor %}\n      </div>\n      <div>\n        <h3>Clientes</h3>\n        {% for key, p in client_profile_templates.items() %}\n        <article class=\"permission-card\"><strong>{{ p.label }}</strong><span>{{ role_labels.get(p.role, p.role) }}</span><p>{{ p.scope }}</p></article>\n        {% endfor %}\n      </div>\n    </div>\n  </div>\n</section>\n\n<section class=\"panel\">\n  <div class=\"panel-title\"><h2>Usuários cadastrados</h2><small>Edite perfil, escopo, vínculo com cliente e projetos atribuídos.</small></div>\n  <div class=\"user-admin-list\">\n    {% for u in users %}\n      <article class=\"user-admin-card\">\n        <div class=\"user-admin-head\">\n          <div><strong>{{ u.name }}</strong><small>{{ u.email }} · {{ u.company_name or 'Atacarejo Insights' }}</small></div>\n          <div><span class=\"status-pill\">{{ profile_label(u.profile_model) }}</span><span class=\"status-pill\">{{ role_labels.get(u.role, u.role) }}</span></div>\n        </div>\n        <p class=\"muted\">Área/função: {{ u.department_area or '-' }} · Escopo: {{ access_levels.get(u.access_scope, u.access_scope or '-') }} · Status: {{ 'Ativo' if u.active else 'Inativo' }}</p>\n        {% if u.assigned_projects %}<p class=\"muted\"><strong>Projetos atribuídos:</strong> {{ u.assigned_projects }}</p>{% endif %}\n        <form method=\"post\" action=\"{{ url_for('user_update', user_id=u.id) }}\" class=\"form-grid compact user-edit-form\">\n          <label>Nome<input name=\"name\" value=\"{{ u.name }}\" required></label>\n          <label>Perfil modelo\n            <select name=\"profile_model\">\n              <optgroup label=\"Perfis internos\">\n                {% for key, p in internal_profile_templates.items() %}<option value=\"{{ key }}\" {% if u.profile_model == key %}selected{% endif %}>{{ p.label }}</option>{% endfor %}\n              </optgroup>\n              <optgroup label=\"Perfis do cliente\">\n                {% for key, p in client_profile_templates.items() %}<option value=\"{{ key }}\" {% if u.profile_model == key %}selected{% endif %}>{{ p.label }}</option>{% endfor %}\n              </optgroup>\n            </select>\n          </label>\n          <label>Papel técnico\n            <select name=\"role\">\n              {% for role_key, role_name in role_labels.items() %}<option value=\"{{ role_key }}\" {% if u.role == role_key %}selected{% endif %}>{{ role_name }}</option>{% endfor %}\n            </select>\n          </label>\n          <label>Área/função<input name=\"department_area\" value=\"{{ u.department_area or '' }}\"></label>\n          <label>Escopo\n            <select name=\"access_scope\">\n              {% for key, label in access_levels.items() %}<option value=\"{{ key }}\" {% if u.access_scope == key %}selected{% endif %}>{{ label }}</option>{% endfor %}\n            </select>\n          </label>\n          <label>Empresa\n            <select name=\"company_id\">\n              <option value=\"\">Sem vínculo / interno</option>\n              {% for c in companies %}<option value=\"{{ c.id }}\" {% if u.company_id == c.id %}selected{% endif %}>{{ c.name }}</option>{% endfor %}\n            </select>\n          </label>\n          <label>Status\n            <select name=\"active\"><option value=\"1\" {% if u.active %}selected{% endif %}>Ativo</option><option value=\"0\" {% if not u.active %}selected{% endif %}>Inativo</option></select>\n          </label>\n          <label>Projetos atribuídos\n            <select name=\"project_ids\" multiple size=\"4\">\n              {% for p in projects %}<option value=\"{{ p.id }}\">{{ p.company_name }} · {{ p.name }}</option>{% endfor %}\n            </select>\n          </label>\n          <label class=\"full\">Observações<textarea name=\"permission_notes\" rows=\"2\">{{ u.permission_notes or '' }}</textarea></label>\n          <div class=\"form-actions\"><button class=\"btn-outline\" type=\"submit\">Salvar ajustes</button></div>\n        </form>\n      </article>\n    {% else %}<p class=\"muted\">Nenhum usuário cadastrado.</p>{% endfor %}\n  </div>\n</section>\n{% endblock %}\n",
  "company_report.html": "{% extends 'base.html' %}\n{% block title %}Relatório · {{ company.name }}{% endblock %}\n{% block content %}\n<header class=\"page-header print-header\">\n  <div>\n    <p class=\"eyebrow\">Relatório executivo</p>\n    <h1>{{ company.name }}</h1>\n    <p>Diagnóstico, projetos, plano de ação e evolução consolidada.</p>\n  </div>\n  <button class=\"btn-primary no-print\" onclick=\"window.print()\">Imprimir / Salvar PDF</button>\n</header>\n\n<section class=\"panel report-cover\">\n  <img src=\"{{ url_for('static', filename='img/logo.png') }}\" alt=\"Atacarejo Insights\">\n  <h2>Relatório de acompanhamento consultivo</h2>\n  <p>Cliente: <strong>{{ company.name }}</strong></p>\n  <p>Segmento: {{ company.segment or '-' }} · {{ company.city or '-' }}/{{ company.state or '-' }}</p>\n</section>\n\n<section class=\"grid-2\">\n  <div class=\"panel\">\n    <h2>Maturidade por área</h2>\n    {% for m in maturity %}\n      <div class=\"maturity-row\"><span>{{ m.name }}</span><div class=\"scorebar\"><i style=\"width: {{ (m.score or 0) * 20 }}%\"></i></div><strong>{{ m.score or 0 }}/5</strong></div>\n      {% if m.comment %}<p class=\"muted smalltext\">{{ m.comment }}</p>{% endif %}\n    {% endfor %}\n  </div>\n  <div class=\"panel\">\n    <h2>Projetos</h2>\n    {% for p in projects %}\n      <article class=\"project-card\"><div><strong>{{ p.name }}</strong><small>{{ p.phase }} · {{ p.status }}</small></div><div class=\"progress\"><span style=\"width: {{ p.progress }}%\"></span></div><span>{{ p.progress }}%</span></article>\n    {% endfor %}\n  </div>\n</section>\n\n<section class=\"panel\">\n  <h2>Plano de ação</h2>\n  <div class=\"table-wrap\">\n    <table><thead><tr><th>Tarefa</th><th>Projeto</th><th>Responsável</th><th>Prazo</th><th>Status</th></tr></thead><tbody>\n      {% for t in tasks %}<tr><td>{{ t.title }}</td><td>{{ t.project_name }}</td><td>{{ t.owner or '-' }}</td><td>{{ t.due_date or '-' }}</td><td>{{ t.status }}</td></tr>{% endfor %}\n    </tbody></table>\n  </div>\n</section>\n{% endblock %}\n",
  "error.html": "{% extends \"base.html\" %}\n{% block title %}{{ code }} - Atacarejo Insights Portal{% endblock %}\n{% block content %}\n<section class=\"hero\" style=\"min-height:70vh;display:flex;align-items:center;justify-content:center;\">\n  <div class=\"card\" style=\"max-width:760px;text-align:center;\">\n    <div class=\"eyebrow\">Atacarejo Insights Portal</div>\n    <h1>{{ title or (code ~ ' - Erro') }}</h1>\n    <p class=\"muted\" style=\"font-size:1.05rem;line-height:1.65;\">{{ message }}</p>\n    <div style=\"display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin-top:22px;\">\n      <a class=\"btn primary\" href=\"{{ url_for('public_home') }}\">Voltar para a página inicial</a>\n      <a class=\"btn ghost\" href=\"{{ url_for('login') }}\">Acessar login</a>\n    </div>\n    <p class=\"muted\" style=\"margin-top:18px;font-size:.85rem;\">Teste técnico: <a href=\"/health\">/health</a> · <a href=\"/health-db\">/health-db</a></p>\n  </div>\n</section>\n{% endblock %}\n",
  "questionnaire_detail.html": "{% extends 'base.html' %}\n{% block title %}{{ questionnaire.title }} · Imersão{% endblock %}\n{% block content %}\n<header class=\"page-header\">\n  <div>\n    <p class=\"eyebrow\">Questionário de imersão · {{ questionnaire.company_name }}</p>\n    <h1>{{ questionnaire.title }}</h1>\n    <p>{{ questionnaire.description or 'Questionário aplicado para coleta estruturada de percepção dos gestores.' }}</p>\n  </div>\n  <a class=\"btn-outline\" href=\"{{ url_for('company_detail', company_id=questionnaire.company_id) }}\">Voltar ao cliente</a>\n</header>\n\n<section class=\"metric-grid small\">\n  <article class=\"metric-card\"><span>Área/contexto</span><strong>{{ questionnaire.context_area or '-' }}</strong></article>\n  <article class=\"metric-card\"><span>Perfil-alvo</span><strong>{{ questionnaire.target_role or '-' }}</strong></article>\n  <article class=\"metric-card accent\"><span>Status</span><strong>{{ questionnaire.status }}</strong></article>\n</section>\n\n{% if g.user.role in ['admin', 'consultant'] %}\n<section class=\"panel collapsible\">\n  <details>\n    <summary>Controle administrativo do questionário</summary>\n    <form method=\"post\" action=\"{{ url_for('questionnaire_status', questionnaire_id=questionnaire.id) }}\" class=\"form-grid compact\">\n      <label>Status\n        <select name=\"status\">\n          {% for s in ['Aberto', 'Em coleta', 'Em análise', 'Fechado'] %}\n          <option value=\"{{ s }}\" {{ 'selected' if questionnaire.status == s else '' }}>{{ s }}</option>\n          {% endfor %}\n        </select>\n      </label>\n      <label>Visível ao cliente\n        <select name=\"visible_to_client\">\n          <option value=\"1\" {{ 'selected' if questionnaire.visible_to_client == 1 else '' }}>Sim</option>\n          <option value=\"0\" {{ 'selected' if questionnaire.visible_to_client != 1 else '' }}>Não</option>\n        </select>\n      </label>\n      <div class=\"form-actions\"><button class=\"btn-primary\" type=\"submit\">Atualizar</button></div>\n    </form>\n  </details>\n</section>\n{% endif %}\n\n<section class=\"grid-2\">\n  <div class=\"panel\">\n    <div class=\"panel-title\">\n      <div>\n        <h2>Respondentes</h2>\n        <p class=\"muted\">Usuários que já contribuíram com este questionário.</p>\n      </div>\n    </div>\n    {% for r in respondents %}\n      <div class=\"user-row\">\n        <div><strong>{{ r.name }}</strong><small>{{ r.email }} · {{ role_labels.get(r.role, r.role) }} · {{ r.answers_count }} resposta(s)</small></div>\n        <span class=\"status-pill\">{{ r.last_answer or '-' }}</span>\n      </div>\n    {% else %}\n      <p class=\"muted\">Nenhum usuário respondeu ainda.</p>\n    {% endfor %}\n  </div>\n\n  <div class=\"panel\">\n    <div class=\"panel-title\"><h2>Minha contribuição</h2></div><p class=\"muted\">Novas respostas entram diretamente. Alterações em respostas já gravadas serão enviadas para aprovação da Atacarejo Insights.</p>\n    {% if g.user.role != 'client_viewer' %}\n    <form method=\"post\" class=\"form-stack questionnaire-form\">\n      {% for question in questions %}\n        {% set mine = my_answers.get(question.id) %}\n        <label>{{ loop.index }}. {{ question.question_text }}\n          <textarea name=\"answer_{{ question.id }}\" rows=\"4\" placeholder=\"Registre a visão da sua área, evidências e exemplos práticos.\">{{ mine.answer_text if mine else '' }}</textarea>\n        </label>\n      {% endfor %}\n      <button class=\"btn-primary\" type=\"submit\">Salvar minhas respostas</button>\n    </form>\n    {% else %}\n      <p class=\"muted\">Seu perfil permite apenas visualização.</p>\n    {% endif %}\n  </div>\n</section>\n\n\n{% if pending_changes and g.user.role in ['admin', 'consultant'] %}\n<section class=\"panel approval-summary\">\n  <div class=\"panel-title\"><h2>Alterações de respostas aguardando aprovação</h2><a href=\"{{ url_for('admin_approvals') }}\">Abrir fila</a></div>\n  <div class=\"cards-row\">\n    {% for cr in pending_changes %}\n    <article class=\"mini-card\">\n      <small>{{ cr.created_at }} · {{ cr.user_name or 'Usuário' }}</small>\n      <strong>{{ cr.field_name }}</strong>\n      <span class=\"status-pill warning\">Pendente</span>\n    </article>\n    {% endfor %}\n  </div>\n</section>\n{% endif %}\n\n<section class=\"panel\">\n  <div class=\"panel-title\">\n    <div>\n      <h2>Respostas registradas por usuário</h2>\n      <p class=\"muted\">Esta visão permite comparar percepções entre Operações, Compras, Vendas, Marketing, Diretoria e demais áreas, mantendo os dados restritos ao cliente.</p>\n    </div>\n  </div>\n  <div class=\"responses-list\">\n    {% for a in answers %}\n      <article class=\"response-card\">\n        <div class=\"response-head\">\n          <div><strong>{{ a.user_name }}</strong><small>{{ a.user_email }} · {{ role_labels.get(a.user_role, a.user_role) }} · {{ a.answered_at }}</small></div>\n          <span class=\"q-area\">Pergunta {{ a.sort_order }}</span>\n        </div>\n        <p class=\"question-text\">{{ a.question_text }}</p>\n        <p>{{ a.answer_text or 'Sem resposta registrada.' }}</p>\n      </article>\n    {% else %}\n      <p class=\"muted\">Ainda não existem respostas para este questionário.</p>\n    {% endfor %}\n  </div>\n</section>\n{% endblock %}\n",
  "stage_detail.html": "{% extends 'base.html' %}\n{% block title %}{{ stage.title }} · Jornada do projeto{% endblock %}\n{% block content %}\n<header class=\"page-header\">\n  <div>\n    <p class=\"eyebrow\">{{ stage.company_name }} · {{ stage.project_name }}</p>\n    <h1>{{ stage.title }}</h1>\n    <p>Informações específicas da etapa selecionada na jornada do projeto.</p>\n  </div>\n  <a class=\"btn-outline\" href=\"{{ url_for('project_detail', project_id=stage.project_id) }}\">Voltar ao projeto</a>\n</header>\n\n<section class=\"panel\">\n  <div class=\"panel-title\">\n    <div>\n      <h2>Jornada do projeto</h2>\n      <p class=\"muted\">Navegação horizontal. Clique em qualquer etapa para abrir os respectivos detalhes.</p>\n    </div>\n  </div>\n  <div class=\"journey-horizontal\" aria-label=\"Jornada horizontal do projeto\">\n    {% for s in stages %}\n      <a class=\"journey-step {{ 'current' if s.id == stage.id else 'done' if s.status == 'Concluída' else 'active' if s.status == 'Em andamento' else 'pending' }}\"\n         href=\"{{ url_for('stage_detail', stage_id=s.id) }}\"\n         title=\"{{ s.status }}\">\n        <span class=\"step-number\">{{ s.sort_order }}</span>\n        <strong>{{ s.title }}</strong>\n      </a>\n    {% endfor %}\n  </div>\n</section>\n\n<section class=\"grid-2\">\n  <article class=\"panel stage-focus-card\">\n    <div class=\"panel-title\">\n      <div>\n        <h2>Detalhes da etapa</h2>\n        <p class=\"muted\">Resumo operacional da fase atual/selecionada.</p>\n      </div>\n      <span class=\"status-pill {{ 'done' if stage.status == 'Concluída' else '' }}\">{{ stage.status }}</span>\n    </div>\n    <div class=\"stage-detail-grid\">\n      <div><span>Projeto</span><strong>{{ stage.project_name }}</strong></div>\n      <div><span>Ordem</span><strong>{{ stage.sort_order }}</strong></div>\n      <div><span>Início</span><strong>{{ stage.start_date or 'Não definido' }}</strong></div>\n      <div><span>Término</span><strong>{{ stage.end_date or 'Não definido' }}</strong></div>\n      <div><span>Progresso geral</span><strong>{{ stage.project_progress }}%</strong></div>\n      <div><span>Status do projeto</span><strong>{{ stage.project_status }}</strong></div>\n    </div>\n    <div class=\"stage-description-box\">\n      <h3>Descrição / informações da etapa</h3>\n      <p>{{ stage.description or 'Nenhuma descrição cadastrada para esta etapa. O administrador pode preencher orientações, entregas esperadas, critérios de conclusão e observações no cadastro da jornada.' }}</p>\n    </div>\n  </article>\n\n  <article class=\"panel\">\n    <div class=\"panel-title\"><h2>Objetivo do projeto</h2></div>\n    <p class=\"readable-text\">{{ stage.project_objective or 'Objetivo do projeto ainda não informado.' }}</p>\n    <div class=\"progress big\"><span style=\"width: {{ stage.project_progress }}%\"></span></div>\n    <p class=\"muted\">Fase textual atual do projeto: <strong>{{ stage.project_phase }}</strong></p>\n  </article>\n</section>\n\n<section class=\"grid-2\">\n  <div class=\"panel\">\n    <div class=\"panel-title\">\n      <div>\n        <h2>Plano de ação relacionado</h2>\n        <p class=\"muted\">Nesta versão, as tarefas ainda são vinculadas ao projeto. Elas aparecem aqui para contextualizar a etapa selecionada.</p>\n      </div>\n    </div>\n    <div class=\"task-list\">\n      {% for t in tasks %}\n      <article class=\"task-item\">\n        <div>\n          <strong>{{ t.title }}</strong>\n          <small>{{ t.description or '' }}</small>\n          <small>Responsável: {{ t.owner or '-' }} · Prazo: {{ t.due_date or '-' }} · Prioridade: {{ t.priority }}</small>\n        </div>\n        <span class=\"status-pill {{ 'done' if t.status == 'Concluída' else '' }}\">{{ t.status }}</span>\n      </article>\n      {% else %}\n        <p class=\"muted\">Nenhuma tarefa cadastrada para este projeto.</p>\n      {% endfor %}\n    </div>\n  </div>\n\n  <div class=\"panel\">\n    <div class=\"panel-title\">\n      <div>\n        <h2>Registros e observações</h2>\n        <p class=\"muted\">Histórico visível para acompanhamento do projeto.</p>\n      </div>\n    </div>\n    <div class=\"notes-list\">\n      {% for n in notes %}\n        <article class=\"note-card\">\n          <strong>{{ n.author_name or 'Atacarejo Insights' }}</strong>\n          <small>{{ n.created_at }} · Visibilidade: {{ n.visibility }}</small>\n          <p>{{ n.note }}</p>\n        </article>\n      {% else %}\n        <p class=\"muted\">Nenhuma observação registrada ainda.</p>\n      {% endfor %}\n    </div>\n  </div>\n</section>\n{% endblock %}\n",
  "client_about.html": "{% extends 'base.html' %}\n{% block title %}Sobre a Atacarejo Insights · Portal do Cliente{% endblock %}\n{% block content %}\n<header class=\"page-header about-hero\">\n  <div>\n    <p class=\"eyebrow\">Atacarejo Insights</p>\n    <h1>Gestão mais inteligente para empresas mais fortes, seguras e competitivas.</h1>\n    <p>Este ambiente explica, de forma direta, como a Atacarejo Insights apoia sua empresa na leitura do negócio, organização de prioridades e acompanhamento da evolução do projeto.</p>\n  </div>\n  <a class=\"btn-outline\" href=\"{{ url_for('client_dashboard') }}\">Voltar ao projeto</a>\n</header>\n\n<section class=\"about-intro panel\">\n  <div class=\"about-logo-box\">\n    <img src=\"{{ url_for('static', filename='img/logo.png') }}\" alt=\"Atacarejo Insights\">\n  </div>\n  <div>\n    <p class=\"eyebrow\">O que somos</p>\n    <h2>Uma consultoria criada para transformar dados, processos e experiência de mercado em decisões práticas.</h2>\n    <p class=\"readable-text\">A Atacarejo Insights atua na estruturação de diagnósticos, indicadores, rotinas de gestão e planos de ação para empresas do varejo alimentar, supermercados, atacarejos e negócios com operação intensiva em compras, abastecimento, logística, loja, margem e sortimento.</p>\n    <p class=\"readable-text\">Nosso trabalho parte de uma ideia simples: negócios mais fortes não dependem apenas de vender mais. Eles precisam comprar melhor, abastecer melhor, precificar melhor, controlar melhor e decidir com mais segurança.</p>\n  </div>\n</section>\n\n<section class=\"grid-2\">\n  {% for insight in content.insights %}\n  <article class=\"panel insight-card\">\n    <span class=\"insight-number\">0{{ loop.index }}</span>\n    <h2>{{ insight.title }}</h2>\n    <p>{{ insight.text }}</p>\n    <small>{{ insight.source }}</small>\n  </article>\n  {% endfor %}\n</section>\n\n<section class=\"panel\">\n  <div class=\"panel-title\">\n    <div>\n      <p class=\"eyebrow\">Como podemos ajudar</p>\n      <h2>Da imersão ao plano de ação: uma jornada para organizar, priorizar e executar.</h2>\n      <p class=\"muted\">O objetivo é transformar a complexidade do negócio em uma visão mais clara de oportunidades, riscos e próximos passos.</p>\n    </div>\n  </div>\n  <div class=\"pillar-grid\">\n    {% for pillar in content.pillars %}\n    <article class=\"pillar-card\">\n      <span>{{ loop.index }}</span>\n      <h3>{{ pillar.title }}</h3>\n      <p>{{ pillar.text }}</p>\n    </article>\n    {% endfor %}\n  </div>\n</section>\n\n<section class=\"grid-2\">\n  <div class=\"panel\">\n    <div class=\"panel-title\"><h2>Metodologia aplicada ao seu projeto</h2></div>\n    <div class=\"method-steps\">\n      {% for step in content.method_steps %}\n      <div class=\"method-step\"><span>{{ loop.index }}</span><strong>{{ step }}</strong></div>\n      {% endfor %}\n    </div>\n  </div>\n  <div class=\"panel accent-panel\">\n    <p class=\"eyebrow\">Por que isso importa</p>\n    <h2>Planejamento bem estruturado reduz improviso e aumenta capacidade de resposta.</h2>\n    <p class=\"readable-text\">No varejo alimentar, ruptura, excesso de estoque, compras desalinhadas, preço mal calibrado, baixa acuracidade de dados e comunicação frágil entre áreas afetam margem, caixa, produtividade e experiência do cliente. Uma empresa mais analítica consegue enxergar antes, priorizar melhor e agir com mais consistência.</p>\n  </div>\n</section>\n\n<section class=\"panel\">\n  <div class=\"panel-title\">\n    <div>\n      <p class=\"eyebrow\">Cases e referências de mercado</p>\n      <h2>O que grandes empresas mostram sobre crescimento e reinvenção</h2>\n    </div>\n  </div>\n  <div class=\"case-grid\">\n    {% for case in content.cases %}\n    <article class=\"case-card\">\n      <h3>{{ case.company }}</h3>\n      <p><strong>Estratégia observada:</strong> {{ case.strategy }}</p>\n      <p><strong>Lição para o projeto:</strong> {{ case.lesson }}</p>\n    </article>\n    {% endfor %}\n  </div>\n</section>\n\n<section class=\"panel references-panel\">\n  <div class=\"panel-title\"><h2>Fontes que orientam nossa leitura do mercado</h2></div>\n  <div class=\"reference-list\">\n    {% for ref in content.references %}\n    <span>{{ ref }}</span>\n    {% endfor %}\n  </div>\n  <p class=\"muted smalltext\">As referências são usadas como base conceitual e setorial. As recomendações finais do projeto serão construídas a partir dos dados, entrevistas, documentos e realidade operacional da sua empresa.</p>\n</section>\n{% endblock %}\n",
  "public_home.html": "{% extends 'base.html' %}\n{% block title %}Atacarejo Insights · Inteligência para varejo alimentar{% endblock %}\n{% block content %}\n<nav class=\"public-nav\">\n  <a class=\"public-brand\" href=\"{{ url_for('index') }}\"><img src=\"{{ url_for('static', filename='img/logo_full_dark.png') }}\" alt=\"Atacarejo Insights\"></a>\n  <div>\n    <a href=\"#mercado\">Mercado</a>\n    <a href=\"#metodologia\">Metodologia</a>\n    <a href=\"#cases\">Cases</a>\n    <a class=\"btn-outline\" href=\"{{ url_for('login') }}\">Acessar portal</a>\n    <a class=\"btn-primary\" href=\"{{ url_for('public_register') }}\">Cadastrar interesse</a>\n  </div>\n</nav>\n\n<section class=\"public-hero\">\n  <div>\n    <p class=\"eyebrow\">Atacarejo Insights</p>\n    <h1>Diagnóstico, dados e estruturação inteligente para supermercados, atacarejos e varejo alimentar.</h1>\n    <p>Uma consultoria criada para ajudar empresas do setor alimentar a organizar informações, fortalecer processos, reduzir riscos e transformar oportunidades em plano de ação acompanhável.</p>\n    <div class=\"public-actions\">\n      <a class=\"btn-primary\" href=\"{{ url_for('public_register') }}\">Cadastrar interesse</a>\n      <a class=\"btn-outline\" href=\"{{ url_for('login') }}\">Já sou cliente</a>\n      <a class=\"btn-outline\" href=\"#metodologia\">Entender a metodologia</a>\n    </div>\n  </div>\n  <div class=\"public-hero-card\">\n    <img src=\"{{ url_for('static', filename='img/logo_full_dark.png') }}\" alt=\"Atacarejo Insights\">\n    <h2>Planejar melhor para competir melhor.</h2>\n    <p>Gestão consultiva com foco em margem, ruptura, abastecimento, compras, sortimento, operação, dados e execução.</p>\n    <p class=\"muted\">Após o contrato, cada usuário recebe login e é direcionado automaticamente ao ambiente permitido.</p>\n  </div>\n</section>\n\n<section class=\"public-section\" id=\"mercado\">\n  <div class=\"section-title\">\n    <p class=\"eyebrow\">Por que isso importa</p>\n    <h2>O varejo alimentar ficou mais dinâmico, competitivo e orientado por dados.</h2>\n    <p>Grandes redes e estudos setoriais apontam uma direção clara: eficiência operacional, leitura do consumidor, integração de canais, supply chain robusto e tomada de decisão baseada em evidências.</p>\n  </div>\n  <div class=\"public-grid-3\">\n    {% for insight in content.insights %}\n      <article class=\"panel insight-card\">\n        <span class=\"insight-number\">0{{ loop.index }}</span>\n        <h2>{{ insight.title }}</h2>\n        <p>{{ insight.text }}</p>\n        <small>{{ insight.source }}</small>\n      </article>\n    {% endfor %}\n  </div>\n</section>\n\n<section class=\"public-section\">\n  <div class=\"section-title\">\n    <p class=\"eyebrow\">Como ajudamos</p>\n    <h2>Da percepção do problema à execução acompanhada.</h2>\n  </div>\n  <div class=\"pillar-grid\">\n    {% for pillar in content.pillars %}\n      <article class=\"pillar-card\">\n        <span>{{ loop.index }}</span>\n        <h3>{{ pillar.title }}</h3>\n        <p>{{ pillar.text }}</p>\n      </article>\n    {% endfor %}\n  </div>\n</section>\n\n<section class=\"public-section grid-2\" id=\"metodologia\">\n  <div class=\"panel accent-panel\">\n    <p class=\"eyebrow\">Metodologia</p>\n    <h2>Uma jornada estruturada para diagnosticar, priorizar e acompanhar.</h2>\n    <p class=\"readable-text\">A Atacarejo Insights combina imersão com gestores, análise de dados, matriz de maturidade, plano de ação e acompanhamento do projeto. A ideia é dar clareza sobre onde a empresa está, quais gargalos mais afetam resultado e quais ações devem ser priorizadas.</p>\n    <a class=\"btn-primary\" href=\"{{ url_for('public_register') }}\">Quero receber contato</a>\n  </div>\n  <div class=\"panel\">\n    <div class=\"method-steps\">\n      {% for step in content.method_steps %}\n        <div class=\"method-step\"><span>{{ loop.index }}</span><strong>{{ step }}</strong></div>\n      {% endfor %}\n    </div>\n  </div>\n</section>\n\n<section class=\"public-section\" id=\"cases\">\n  <div class=\"section-title\">\n    <p class=\"eyebrow\">Referências e inspiração</p>\n    <h2>Grandes redes crescem porque se reinventam sem perder disciplina operacional.</h2>\n  </div>\n  <div class=\"case-grid\">\n    {% for case in content.cases %}\n      <article class=\"case-card\">\n        <h3>{{ case.company }}</h3>\n        <p><strong>Estratégia:</strong> {{ case.strategy }}</p>\n        <p><strong>Lição:</strong> {{ case.lesson }}</p>\n      </article>\n    {% endfor %}\n  </div>\n</section>\n\n<section class=\"public-section references-panel panel\">\n  <div class=\"panel-title\"><h2>Referências utilizadas nos conteúdos e insights</h2></div>\n  <div class=\"reference-list\">\n    {% for ref in content.references %}<span>{{ ref }}</span>{% endfor %}\n  </div>\n  <p class=\"muted\">Essas referências orientam o conteúdo institucional e a lógica consultiva. O diagnóstico de cada cliente é feito individualmente, com dados, entrevistas e evidências da própria operação.</p>\n</section>\n\n<section class=\"public-cta\">\n  <h2>Quer entender onde seu negócio pode ganhar eficiência, margem e segurança gerencial?</h2>\n  <p>Cadastre seu interesse. A Atacarejo Insights fará contato para entender seu cenário, maturidade atual e possibilidades de projeto.</p>\n  <a class=\"btn-primary\" href=\"{{ url_for('public_register') }}\">Cadastrar interesse</a>\n</section>\n{% endblock %}\n",
  "lead_register.html": "{% extends 'base.html' %}\n{% block title %}Cadastro de interesse · Atacarejo Insights{% endblock %}\n{% block content %}\n<nav class=\"public-nav\">\n  <a class=\"public-brand\" href=\"{{ url_for('index') }}\"><img src=\"{{ url_for('static', filename='img/logo_full_dark.png') }}\" alt=\"Atacarejo Insights\"></a>\n  <div><a href=\"{{ url_for('index') }}\">Página inicial</a><a class=\"btn-outline\" href=\"{{ url_for('login') }}\">Login</a></div>\n</nav>\n\n<section class=\"register-shell\">\n  <div class=\"panel register-panel\">\n    {% if success %}\n      <p class=\"eyebrow\">Cadastro recebido</p>\n      <h1>Obrigado pelo interesse na Atacarejo Insights.</h1>\n      <p class=\"readable-text\">Seu cadastro foi registrado. Nossa equipe entrará em contato para entender o momento da empresa, apresentar a proposta de atuação e avaliar a aderência para uma reunião de diagnóstico.</p>\n      <p class=\"muted-note\">Os dados completos da empresa serão incluídos depois, durante a etapa comercial e após a formalização do contrato de prestação de serviço.</p>\n      <a class=\"btn-primary\" href=\"{{ url_for('index') }}\">Voltar à página inicial</a>\n    {% else %}\n      <p class=\"eyebrow\">Primeiro contato</p>\n      <h1>Cadastre sua empresa para receber contato.</h1>\n      <p class=\"muted\">Nesta etapa inicial coletamos somente os dados essenciais para contato. As demais informações serão tratadas em reunião com a equipe da Atacarejo Insights e, após contratação, no ambiente seguro do cliente.</p>\n      <form method=\"post\" class=\"form-grid compact\">\n        <label>Nome do solicitante<input name=\"contact_name\" required placeholder=\"Nome de quem está solicitando contato\"></label>\n        <label>Nome da empresa<input name=\"company_name\" required placeholder=\"Razão social ou nome fantasia\"></label>\n        <label>Estado da matriz\n          <select name=\"state\" required>\n            <option value=\"\">Selecione</option>\n            {% for uf in ['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'] %}\n            <option value=\"{{ uf }}\">{{ uf }}</option>\n            {% endfor %}\n          </select>\n        </label>\n        <label>Telefone/WhatsApp<input name=\"contact_phone\" required placeholder=\"(00) 00000-0000\"></label>\n        <label class=\"full\">E-mail para contato<input name=\"contact_email\" type=\"email\" required placeholder=\"nome@empresa.com.br\"></label>\n        <div class=\"form-actions\"><button class=\"btn-primary\" type=\"submit\">Solicitar contato</button></div>\n      </form>\n    {% endif %}\n  </div>\n</section>\n{% endblock %}\n",
  "admin_leads.html": "{% extends 'base.html' %}\n{% block title %}Leads do site · Atacarejo Insights{% endblock %}\n{% block content %}\n<header class=\"page-header\">\n  <div>\n    <p class=\"eyebrow\">Comercial</p>\n    <h1>Leads captados pelo site</h1>\n    <p>Cadastros de primeiro contato vindos da landing page, redes sociais, flyers e divulgações.</p>\n  </div>\n</header>\n<section class=\"panel\">\n  <div class=\"panel-title\">\n    <h2>Solicitações de contato</h2>\n    <small>Dados completos serão adicionados somente após reunião, apresentação do projeto e formalização contratual.</small>\n  </div>\n  <div class=\"table-wrap\">\n    <table>\n      <thead><tr><th>Empresa</th><th>Solicitante</th><th>Contato</th><th>Status</th><th>Ações</th></tr></thead>\n      <tbody>\n        {% for l in leads %}\n        <tr>\n          <td><strong>{{ l.company_name }}</strong><br><small>Matriz: {{ l.state or '-' }}</small></td>\n          <td>{{ l.contact_name }}<br><small>Origem: {{ l.source or 'Site' }}</small></td>\n          <td><small>{{ l.contact_phone or '-' }}</small><br><small>{{ l.contact_email }}</small></td>\n          <td><span class=\"status-pill\">{{ l.status }}</span><br><small>{{ l.created_at }}</small></td>\n          <td>\n            <form method=\"post\" class=\"lead-actions\">\n              <input type=\"hidden\" name=\"lead_id\" value=\"{{ l.id }}\">\n              <select name=\"status\"><option>Novo lead</option><option>Contato realizado</option><option>Reunião marcada</option><option>Projeto apresentado</option><option>Em negociação</option><option>Sem aderência</option><option>Convertido em cliente</option></select>\n              <button class=\"btn-outline\" type=\"submit\">Atualizar</button>\n            </form>\n            {% if l.status != 'Convertido em cliente' %}\n            <form method=\"post\" action=\"{{ url_for('admin_lead_convert', lead_id=l.id) }}\" class=\"lead-actions\">\n              <input name=\"password\" placeholder=\"Senha inicial\" value=\"cliente123\">\n              <button class=\"btn-primary\" type=\"submit\">Converter em cliente</button>\n            </form>\n            {% endif %}\n          </td>\n        </tr>\n        {% else %}<tr><td colspan=\"5\">Nenhum lead cadastrado pelo site.</td></tr>{% endfor %}\n      </tbody>\n    </table>\n  </div>\n</section>\n{% endblock %}\n",
  "admin_approvals.html": "{% extends 'base.html' %}\n{% block title %}Aprovações · Atacarejo Insights{% endblock %}\n{% block content %}\n<header class=\"page-header\">\n  <div>\n    <p class=\"eyebrow\">Governança de dados</p>\n    <h1>Aprovações pendentes</h1>\n    <p>Alterações cadastrais, edições de respostas e informações enviadas por usuários do cliente entram aqui antes de alterar oficialmente o ambiente do projeto.</p>\n  </div>\n</header>\n\n<section class=\"panel\">\n  <div class=\"panel-title\"><h2>Fila de aprovação</h2></div>\n  <div class=\"approval-list\">\n    {% for r in pending %}\n    <article class=\"approval-card\">\n      <div class=\"approval-head\">\n        <div><strong>{{ r.company_name }}</strong><small>{{ r.created_at }} · {{ r.user_name or 'Usuário' }} · {{ r.user_email or '' }}</small></div>\n        <span class=\"status-pill warning\">{{ r.entity_type }}</span>\n      </div>\n      <p><strong>Campo:</strong> {{ r.field_name }}</p>\n      <div class=\"approval-values\">\n        <div><span>Valor atual</span><p>{{ r.old_value or '—' }}</p></div>\n        <div><span>Novo valor solicitado</span><p>{{ r.new_value or '—' }}</p></div>\n      </div>\n      <form method=\"post\" action=\"{{ url_for('admin_approval_action', request_id=r.id, action='approve') }}\" class=\"approval-actions\">\n        <input name=\"admin_note\" placeholder=\"Observação opcional\">\n        <button class=\"btn-primary\" type=\"submit\">Aprovar</button>\n      </form>\n      <form method=\"post\" action=\"{{ url_for('admin_approval_action', request_id=r.id, action='reject') }}\" class=\"approval-actions\">\n        <input name=\"admin_note\" placeholder=\"Motivo da rejeição\">\n        <button class=\"btn-outline\" type=\"submit\">Rejeitar</button>\n      </form>\n    </article>\n    {% else %}<p class=\"muted\">Não há aprovações pendentes.</p>{% endfor %}\n  </div>\n</section>\n\n<section class=\"panel\">\n  <div class=\"panel-title\"><h2>Últimas revisões</h2></div>\n  <div class=\"table-wrap\"><table><thead><tr><th>Cliente</th><th>Campo</th><th>Status</th><th>Revisado em</th><th>Observação</th></tr></thead><tbody>\n    {% for r in reviewed %}<tr><td>{{ r.company_name }}</td><td>{{ r.field_name }}</td><td><span class=\"status-pill {{ 'done' if r.status == 'Aprovada' else '' }}\">{{ r.status }}</span></td><td>{{ r.reviewed_at }}</td><td>{{ r.admin_note or '-' }}</td></tr>{% else %}<tr><td colspan=\"5\">Sem revisões registradas.</td></tr>{% endfor %}\n  </tbody></table></div>\n</section>\n{% endblock %}\n",
  "client_company_edit.html": "{% extends 'base.html' %}\n{% block title %}Alterações cadastrais · Atacarejo Insights{% endblock %}\n{% block content %}\n<header class=\"page-header\">\n  <div>\n    <p class=\"eyebrow\">Ambiente do cliente</p>\n    <h1>Solicitar alteração cadastral</h1>\n    <p>Por segurança e confidencialidade, alterações feitas por usuários do cliente entram em aprovação antes de atualizar oficialmente o cadastro.</p>\n  </div>\n</header>\n<section class=\"grid-2\">\n  <div class=\"panel\">\n    <div class=\"panel-title\"><h2>Dados atuais</h2></div>\n    <form method=\"post\" class=\"form-grid compact\">\n      <label>Empresa<input name=\"name\" value=\"{{ company.name }}\"></label>\n      <label>CNPJ<input name=\"cnpj\" value=\"{{ company.cnpj or '' }}\"></label>\n      <label>Segmento<input name=\"segment\" value=\"{{ company.segment or '' }}\"></label>\n      <label>Número de lojas<input name=\"stores\" type=\"number\" value=\"{{ company.stores or 0 }}\"></label>\n      <label>Cidade<input name=\"city\" value=\"{{ company.city or '' }}\"></label>\n      <label>UF<input name=\"state\" value=\"{{ company.state or '' }}\"></label>\n      <label>Faturamento mensal estimado<input name=\"monthly_revenue\" type=\"number\" step=\"0.01\" value=\"{{ company.monthly_revenue or 0 }}\"></label>\n      <label>Responsável principal<input name=\"contact_name\" value=\"{{ company.contact_name or '' }}\"></label>\n      <label class=\"full\">E-mail principal<input name=\"contact_email\" value=\"{{ company.contact_email or '' }}\"></label>\n      <div class=\"form-actions\"><button class=\"btn-primary\" type=\"submit\">Enviar alterações para aprovação</button></div>\n    </form>\n  </div>\n  <div class=\"panel\">\n    <div class=\"panel-title\"><h2>Histórico de solicitações</h2></div>\n    <div class=\"approval-list compact-list\">\n      {% for p in pending %}\n      <article class=\"approval-card small-card\">\n        <div class=\"approval-head\"><strong>{{ p.field_name }}</strong><span class=\"status-pill {{ 'done' if p.status == 'Aprovada' else 'warning' if p.status == 'Pendente' else '' }}\">{{ p.status }}</span></div>\n        <small>{{ p.created_at }}</small>\n        <p><strong>De:</strong> {{ p.old_value or '—' }}</p>\n        <p><strong>Para:</strong> {{ p.new_value or '—' }}</p>\n        {% if p.admin_note %}<p><strong>Observação:</strong> {{ p.admin_note }}</p>{% endif %}\n      </article>\n      {% else %}<p class=\"muted\">Nenhuma solicitação registrada.</p>{% endfor %}\n    </div>\n  </div>\n</section>\n{% endblock %}\n",
  "client_users.html": "{% extends 'base.html' %}\n{% block title %}Usuários do cliente · Atacarejo Insights{% endblock %}\n{% block content %}\n<header class=\"page-header\">\n  <div>\n    <p class=\"eyebrow\">Acessos da empresa</p>\n    <h1>Usuários do cliente</h1>\n    <p>Solicite novos usuários para sua empresa. Por segurança e confidencialidade, a Atacarejo Insights revisa e aprova a criação antes da liberação definitiva.</p>\n  </div>\n</header>\n\n<section class=\"grid-2\">\n  <div class=\"panel\">\n    <div class=\"panel-title\"><h2>Solicitar novo usuário</h2><small>A solicitação ficará pendente de aprovação administrativa.</small></div>\n    <form method=\"post\" class=\"form-stack\">\n      <label>Nome<input name=\"name\" required></label>\n      <label>E-mail<input name=\"email\" type=\"email\" required></label>\n      <label>Senha inicial sugerida<input name=\"password\" type=\"password\" placeholder=\"Padrão: cliente123\"></label>\n      <label>Perfil do cliente\n        <select name=\"profile_model\" required>\n          {% for key, p in client_profile_templates.items() %}<option value=\"{{ key }}\">{{ p.label }}</option>{% endfor %}\n        </select>\n      </label>\n      <label>Área/função<input name=\"department_area\" placeholder=\"Ex.: Operações, Compras, Marketing, Diretoria...\"></label>\n      <label>Escopo de acesso\n        <select name=\"access_scope\">\n          <option value=\"company_only\">Somente empresa vinculada</option>\n          <option value=\"area_only\">Somente área/função informada</option>\n          <option value=\"read_only\">Somente visualização</option>\n        </select>\n      </label>\n      <label>Observações<textarea name=\"permission_notes\" rows=\"3\" placeholder=\"Ex.: responderá apenas questionários de compras; visualizará relatórios executivos...\"></textarea></label>\n      <button class=\"btn-primary\" type=\"submit\">Enviar para aprovação</button>\n    </form>\n  </div>\n\n  <div class=\"panel\">\n    <div class=\"panel-title\"><h2>Usuários ativos da empresa</h2></div>\n    {% for u in company_users %}\n      <div class=\"user-row\">\n        <div><strong>{{ u.name }}</strong><small>{{ u.email }} · {{ u.department_area or '-' }}</small><small>{{ access_levels.get(u.access_scope, u.access_scope or 'Escopo padrão') }}</small></div>\n        <span class=\"status-pill\">{{ profile_label(u.profile_model) }}</span>\n      </div>\n    {% else %}<p class=\"muted\">Nenhum usuário vinculado.</p>{% endfor %}\n  </div>\n</section>\n\n<section class=\"panel\">\n  <div class=\"panel-title\"><h2>Solicitações enviadas</h2><small>Histórico de pedidos de criação de usuários.</small></div>\n  <div class=\"table-wrap\">\n    <table>\n      <thead><tr><th>Solicitação</th><th>Status</th><th>Data</th><th>Observação da Atacarejo</th></tr></thead>\n      <tbody>\n        {% for r in pending %}\n        <tr>\n          <td>{{ r.field_name }}<br><small>{{ r.new_value }}</small></td>\n          <td><span class=\"status-pill\">{{ r.status }}</span></td>\n          <td>{{ r.created_at }}</td>\n          <td>{{ r.admin_note or '-' }}</td>\n        </tr>\n        {% else %}<tr><td colspan=\"4\">Nenhuma solicitação de usuário registrada.</td></tr>{% endfor %}\n      </tbody>\n    </table>\n  </div>\n</section>\n{% endblock %}\n"
}

def configure_template_loader():
    templates_dir = os.path.join(BASE_DIR, "templates")
    loaders = []
    if os.path.isdir(templates_dir):
        loaders.append(FileSystemLoader(templates_dir))
    loaders.append(DictLoader(EMBEDDED_TEMPLATES))
    app.jinja_loader = ChoiceLoader(loaders)
    print(
        f"[Atacarejo Insights] Template loader configurado. "
        f"templates_dir={templates_dir} exists={os.path.isdir(templates_dir)} "
        f"embedded={len(EMBEDDED_TEMPLATES)}",
        file=sys.stderr,
    )

configure_template_loader()

ADMIN_ROLES = {"admin", "consultant"}
CLIENT_ROLES = {"client_admin", "client_collaborator", "client_viewer"}

INTERNAL_PROFILE_TEMPLATES = {
    "admin_geral": {
        "label": "Administrador geral",
        "role": "admin",
        "scope": "Acesso total a clientes, leads, aprovações, usuários, contratos, projetos e configurações."
    },
    "gestor_projeto": {
        "label": "Gestor de projeto",
        "role": "consultant",
        "scope": "Acompanha clientes e projetos atribuídos, gerencia tarefas, etapas, ritos e entregas."
    },
    "analista_inteligencia": {
        "label": "Analista de inteligência/dados",
        "role": "consultant",
        "scope": "Apoia diagnósticos, indicadores, dashboards, bases de dados, pesquisas e relatórios."
    },
    "analista_supply": {
        "label": "Analista de supply/compras",
        "role": "consultant",
        "scope": "Atua em compras, abastecimento, sortimento, ruptura, estoque, demanda e fornecedores."
    },
    "analista_logistica": {
        "label": "Analista de logística/distribuição",
        "role": "consultant",
        "scope": "Atua em CD, transportes, roteirização, nível de serviço, frota, expedição e entregas."
    },
    "analista_financeiro": {
        "label": "Analista financeiro/controladoria",
        "role": "consultant",
        "scope": "Atua em DRE gerencial, margem, custos, fluxo de caixa, indicadores econômicos e produtividade."
    },
    "atendimento_comercial": {
        "label": "Atendimento/comercial",
        "role": "consultant",
        "scope": "Acompanha leads, cadastros iniciais, reuniões comerciais e evolução pré-contratual."
    },
}

CLIENT_PROFILE_TEMPLATES = {
    "cliente_master": {
        "label": "Cliente gestor master",
        "role": "client_admin",
        "scope": "Gerencia usuários do cliente, dados cadastrais, respostas, documentos e acompanhamento geral do projeto."
    },
    "diretor_executivo": {
        "label": "Diretor executivo",
        "role": "client_admin",
        "scope": "Acompanha visão executiva, jornada, relatórios, aprovações internas do cliente e informações estratégicas."
    },
    "gestor_area": {
        "label": "Gestor de área",
        "role": "client_collaborator",
        "scope": "Responde questionários e envia informações da própria área, com visão do projeto do cliente."
    },
    "colaborador_respondente": {
        "label": "Colaborador respondente",
        "role": "client_collaborator",
        "scope": "Preenche formulários, fornece evidências e acompanha pendências atribuídas ao cliente."
    },
    "visualizador_executivo": {
        "label": "Visualizador executivo",
        "role": "client_viewer",
        "scope": "Visualiza informações liberadas, etapas, relatórios e status, sem alterar dados."
    },
}

PROFILE_TEMPLATES = {**INTERNAL_PROFILE_TEMPLATES, **CLIENT_PROFILE_TEMPLATES}

ACCESS_LEVELS = {
    "total": "Acesso total",
    "assigned_projects": "Somente projetos atribuídos",
    "company_only": "Somente empresa vinculada",
    "area_only": "Somente área/função informada",
    "read_only": "Somente visualização",
}


def profile_to_role(profile_model, fallback_role=None):
    if profile_model and profile_model in PROFILE_TEMPLATES:
        return PROFILE_TEMPLATES[profile_model]["role"]
    return fallback_role or "client_viewer"


def profile_label(profile_model):
    if profile_model and profile_model in PROFILE_TEMPLATES:
        return PROFILE_TEMPLATES[profile_model]["label"]
    return profile_model or "Perfil não definido"

AREAS = [
    ("Estratégia e Diretoria", "Direção estratégica, prioridades, governança executiva, metas, indicadores e tomada de decisão."),
    ("Governança e Processos", "Padronização, ritos de gestão, políticas internas, documentação, alçadas e responsabilidades."),
    ("Operação de loja", "Rotina de loja, execução, exposição, produtividade, perdas, atendimento e aderência a padrões."),
    ("Comercial e Vendas", "Gestão de vendas, metas, campanhas, performance por loja/canal e execução comercial."),
    ("Marketing", "Comunicação, marca, campanhas, relacionamento com clientes e posicionamento institucional."),
    ("Trade Marketing", "Calendário promocional, execução de campanhas, verbas comerciais, planogramas e ativações no ponto de venda."),
    ("Compras", "Governança de compras, negociação, fornecedores, calendário comercial, verbas e condições comerciais."),
    ("Gestão de Categorias e Sortimento", "Mix por loja, curva ABC, categorias críticas, regionalização, racionalização de SKUs e performance por categoria."),
    ("Pricing e Margem", "Formação de preços, competitividade, elasticidade, margem, remarcações e arquitetura de preço."),
    ("Abastecimento e Reposição", "Pedido, reposição, ruptura, cobertura, estoque de segurança, giro e aderência à demanda."),
    ("Supply Chain", "Integração entre compras, demanda, estoque, logística, abastecimento, distribuição e operação."),
    ("Planejamento de Demanda e S&OP", "Previsão de demanda, sazonalidade, planejamento integrado, consensos e ritos de S&OP."),
    ("Logística", "Estratégia logística, custos, nível de serviço, CD, transporte, rotas e integração com lojas."),
    ("Distribuição e Transportes", "Roteirização, frota, frequência de entrega, ocupação, produtividade e nível de serviço de distribuição."),
    ("Centro de Distribuição e Armazenagem", "Recebimento, armazenagem, separação, expedição, acuracidade, inventário e produtividade do CD."),
    ("Estoque e Inventário", "Acuracidade, inventários, divergências, cobertura, perdas, sobras e controles físicos/sistêmicos."),
    ("Prevenção de Perdas", "Quebras, furtos, avarias, vencimentos, controles preventivos e ações corretivas."),
    ("Financeiro e Tesouraria", "Fluxo de caixa, contas a pagar/receber, conciliação, capital de giro e controles financeiros."),
    ("Controladoria", "Orçamento, DRE gerencial, centros de custo, indicadores econômicos e análise de resultado."),
    ("Contabilidade", "Fechamento contábil, registros, conciliações, demonstrações e suporte à gestão."),
    ("Fiscal e Tributário", "Apuração fiscal, obrigações acessórias, compliance tributário, créditos, regimes e impactos por UF."),
    ("Recursos Humanos", "Estrutura organizacional, recrutamento, treinamento, clima, liderança, produtividade e desenvolvimento."),
    ("Departamento Pessoal", "Folha, ponto, benefícios, admissões, desligamentos, jornadas e conformidade trabalhista."),
    ("Tecnologia da Informação", "Sistemas, infraestrutura, integrações, segurança, disponibilidade e suporte aos usuários."),
    ("BI, Dados e Inteligência de Mercado", "Dashboards, governança de dados, indicadores, análises, pesquisas e tomada de decisão orientada por evidências."),
    ("E-commerce e Omnichannel", "Vendas digitais, integração loja/site/app, retirada, entrega, jornada digital e indicadores online."),
    ("Atendimento ao Cliente e CRM", "SAC, NPS, reclamações, fidelização, base de clientes, relacionamento e experiência do consumidor."),
    ("Expansão e Novos Negócios", "Novas lojas, estudos de mercado, viabilidade, localização, expansão regional e pipeline de crescimento."),
    ("Jurídico e Compliance", "Contratos, riscos legais, políticas, compliance, LGPD, auditorias e governança corporativa."),
    ("Qualidade e Segurança Alimentar", "Boas práticas, vigilância sanitária, qualidade de perecíveis, rastreabilidade e controle de validade."),
    ("Manutenção e Facilities", "Manutenção predial, equipamentos, refrigeração, energia, facilities e disponibilidade operacional."),
    ("ESG e Sustentabilidade", "Resíduos, energia, impacto social, práticas ambientais, indicadores ESG e reputação institucional."),
]

AREA_QUESTION_TEMPLATES = {
    "Estratégia e Diretoria": [
        "Quais são as principais prioridades estratégicas da empresa para os próximos 12 meses?",
        "Quais decisões críticas ainda são tomadas com baixa disponibilidade de dados ou pouca padronização?",
        "Quais indicadores a diretoria acompanha com maior frequência e quais deveriam ser criados ou melhorados?",
        "Quais riscos mais preocupam a liderança hoje em margem, crescimento, operação ou caixa?",
        "Ao final do projeto, quais entregas comprovariam valor para a diretoria?",
    ],
    "Governança e Processos": [
        "Quais processos críticos ainda dependem de conhecimento informal ou pessoas específicas?",
        "Existem políticas, alçadas, fluxos e responsáveis formalmente documentados?",
        "Como são acompanhadas pendências, decisões, planos de ação e responsáveis?",
        "Quais ritos de gestão existem hoje e quais áreas participam deles?",
        "Onde a falta de padronização mais gera retrabalho, atraso ou perda de resultado?",
    ],
    "Operação de loja": [
        "Quais gargalos operacionais mais impactam a rotina das lojas?",
        "Como a liderança acompanha execução, ruptura, perdas, produtividade e atendimento?",
        "Quais rotinas de loja são padronizadas e auditadas?",
        "Como problemas identificados em loja retornam para compras, abastecimento e logística?",
        "Quais oportunidades poderiam gerar impacto rápido nos próximos 90 dias?",
    ],
    "Comercial e Vendas": [
        "Como são definidas metas comerciais por loja, categoria e período?",
        "Quais indicadores de venda são acompanhados diariamente e semanalmente?",
        "Como a empresa avalia performance de campanhas, ofertas e ações comerciais?",
        "Quais canais, lojas ou categorias apresentam maior oportunidade de crescimento?",
        "Como a área comercial se alinha com compras, operação, marketing e pricing?",
    ],
    "Marketing": [
        "Como o calendário de comunicação é construído e validado?",
        "Quais canais de comunicação trazem melhor retorno percebido?",
        "Como a marca acompanha posicionamento, percepção do cliente e concorrência?",
        "Como os resultados das campanhas são mensurados após a execução?",
        "Quais informações faltam para melhorar a efetividade das ações de marketing?",
    ],
    "Trade Marketing": [
        "Como são planejadas ativações no ponto de venda e campanhas com fornecedores?",
        "Como a execução das ações é acompanhada nas lojas?",
        "Existe controle de verbas comerciais, materiais, acordos e contrapartidas?",
        "Como trade se integra com compras, marketing, operação e categorias?",
        "Quais oportunidades existem para melhorar execução promocional e exposição?",
    ],
    "Compras": [
        "Como é definido o calendário de compras e negociações comerciais?",
        "Quais critérios priorizam fornecedores, categorias e oportunidades de negociação?",
        "Como compras acompanha ruptura, excesso de estoque, margem e cobertura?",
        "Quais informações faltam para melhorar a tomada de decisão em compras?",
        "Quais categorias exigem atenção imediata por margem, giro, ruptura ou competitividade?",
    ],
    "Gestão de Categorias e Sortimento": [
        "Como o mix é definido por loja, cluster, região ou perfil de consumidor?",
        "Como a empresa decide inclusão, manutenção ou descontinuação de SKUs?",
        "Existe análise de curva ABC, margem, giro, ruptura e espaço por categoria?",
        "Quais categorias têm maior desalinhamento entre sortimento, demanda e rentabilidade?",
        "Como as decisões de categoria se conectam com compras, pricing e operação?",
    ],
    "Pricing e Margem": [
        "Como os preços são formados, revisados e aprovados?",
        "Como a empresa monitora preço da concorrência e posicionamento por categoria?",
        "Quais indicadores de margem são acompanhados por loja, categoria e fornecedor?",
        "Como são tratadas perdas de margem por oferta, ruptura, remarcação ou erro cadastral?",
        "Quais decisões de preço poderiam ser mais orientadas por dados?",
    ],
    "Abastecimento e Reposição": [
        "Como os pedidos são gerados, revisados e aprovados?",
        "Como são definidos parâmetros de estoque, cobertura e frequência de reposição?",
        "Como a empresa identifica e trata ruptura, excesso e baixo giro?",
        "Quais dados são usados para ajustar pedidos em datas sazonais ou campanhas?",
        "Quais gargalos mais afetam disponibilidade de produtos nas lojas?",
    ],
    "Supply Chain": [
        "Como compras, demanda, estoque, logística e operação se integram no planejamento?",
        "Quais indicadores medem nível de serviço, custo, estoque, ruptura e produtividade?",
        "Onde ocorrem os maiores conflitos entre disponibilidade, margem, custo e capital de giro?",
        "Como decisões de compras impactam CD, transporte, lojas e fluxo de caixa?",
        "Quais rotinas deveriam ser integradas em uma governança de supply chain?",
    ],
    "Planejamento de Demanda e S&OP": [
        "Existe processo formal de previsão de demanda e consenso entre áreas?",
        "Como sazonalidade, campanhas, ruptura e eventos externos são considerados no planejamento?",
        "Quais dados alimentam as previsões e com que frequência são revisados?",
        "Como divergências entre planejado e realizado são analisadas?",
        "Quais decisões deveriam fazer parte de um rito mensal de S&OP?",
    ],
    "Logística": [
        "Quais são os principais custos e gargalos logísticos atuais?",
        "Como a empresa mede nível de serviço, lead time, produtividade e custo por entrega?",
        "Quais problemas logísticos mais impactam loja, abastecimento ou experiência do cliente?",
        "Como são priorizadas melhorias em CD, transporte, rotas e frequência de entrega?",
        "Quais indicadores logísticos deveriam ser acompanhados em rotina executiva?",
    ],
    "Distribuição e Transportes": [
        "Como são definidas rotas, janelas, frequência e capacidade de entrega?",
        "Como a ocupação da frota, custo por rota e produtividade são monitorados?",
        "Quais atrasos, devoluções ou ocorrências mais afetam o nível de serviço?",
        "Como lojas sinalizam problemas de entrega e como eles são tratados?",
        "Quais oportunidades existem para melhorar roteirização, frota ou performance de transportes?",
    ],
    "Centro de Distribuição e Armazenagem": [
        "Como estão estruturados recebimento, armazenagem, separação e expedição?",
        "Quais indicadores de produtividade e acuracidade são acompanhados no CD?",
        "Quais gargalos mais geram atraso, erro, avaria ou retrabalho?",
        "Como o CD lida com sazonalidade, campanhas e picos de volume?",
        "Quais melhorias físicas, sistêmicas ou processuais são mais urgentes?",
    ],
    "Estoque e Inventário": [
        "Como a empresa mede acuracidade de estoque físico versus sistêmico?",
        "Quais são as principais causas de divergências, sobras, faltas e ajustes?",
        "Como são planejados inventários gerais, rotativos e cíclicos?",
        "Como problemas de estoque impactam compras, abastecimento e operação de loja?",
        "Quais controles deveriam ser reforçados nos próximos 90 dias?",
    ],
    "Prevenção de Perdas": [
        "Quais categorias, lojas ou processos concentram maior perda conhecida ou desconhecida?",
        "Como são acompanhadas quebras, vencimentos, avarias, furtos e divergências?",
        "Quais controles preventivos existem hoje e quais são pouco aderentes?",
        "Como prevenção de perdas se integra com operação, estoque, segurança e compras?",
        "Quais ações teriam maior impacto rápido na redução de perdas?",
    ],
    "Financeiro e Tesouraria": [
        "Como a empresa acompanha fluxo de caixa, contas a pagar e receber?",
        "Quais relatórios financeiros são usados na tomada de decisão diária e mensal?",
        "Como compras, estoque e prazo de fornecedores impactam capital de giro?",
        "Quais conciliações, controles ou indicadores precisam ser aprimorados?",
        "Quais riscos financeiros devem ser monitorados durante o projeto?",
    ],
    "Controladoria": [
        "Como a empresa acompanha DRE gerencial, orçamento e centros de custo?",
        "Quais indicadores mostram rentabilidade por loja, categoria ou unidade de negócio?",
        "Como desvios entre orçamento e realizado são analisados e tratados?",
        "Quais informações faltam para avaliar margem, custo e produtividade com precisão?",
        "Como a controladoria participa dos ritos de gestão e decisões estratégicas?",
    ],
    "Contabilidade": [
        "Como são realizados fechamentos, conciliações e validações contábeis?",
        "Quais pontos geram maior retrabalho ou atraso no fechamento?",
        "Como informações contábeis são integradas à visão gerencial do negócio?",
        "Quais riscos de inconsistência cadastral, fiscal ou operacional chegam à contabilidade?",
        "Quais melhorias ajudariam a tornar os dados mais confiáveis para gestão?",
    ],
    "Fiscal e Tributário": [
        "Quais tributos, obrigações e regimes demandam maior atenção na operação?",
        "Como são tratados cadastros fiscais de produtos, NCM, CST/CSOSN e alíquotas?",
        "Existem oportunidades de créditos, revisão tributária ou prevenção de autuações?",
        "Como mudanças fiscais por UF impactam compras, preço e margem?",
        "Quais controles fiscais deveriam estar integrados ao diagnóstico de dados?",
    ],
    "Recursos Humanos": [
        "Como está estruturada a equipe por área, loja e nível hierárquico?",
        "Quais indicadores de turnover, absenteísmo, treinamento e produtividade são acompanhados?",
        "Quais cargos ou áreas apresentam maior dificuldade de contratação ou retenção?",
        "Como líderes são desenvolvidos e acompanhados em rotina de gestão?",
        "Quais iniciativas de RH teriam maior impacto sobre produtividade e clima?",
    ],
    "Departamento Pessoal": [
        "Como são controlados ponto, jornada, banco de horas, benefícios e folha?",
        "Quais processos de admissão, férias, afastamentos e desligamentos geram maior retrabalho?",
        "Existem riscos trabalhistas recorrentes relacionados à operação?",
        "Como DP se integra com RH, líderes e operação de loja?",
        "Quais controles precisam ser reforçados para reduzir risco e melhorar eficiência?",
    ],
    "Tecnologia da Informação": [
        "Quais sistemas sustentam vendas, compras, estoque, financeiro e operação?",
        "Quais integrações existem e onde ocorrem falhas ou retrabalhos manuais?",
        "Como são tratados segurança, acessos, backups e disponibilidade dos sistemas?",
        "Quais limitações tecnológicas dificultam análise de dados e gestão por indicadores?",
        "Quais melhorias sistêmicas seriam prioritárias para apoiar o projeto?",
    ],
    "BI, Dados e Inteligência de Mercado": [
        "Quais dashboards e relatórios são usados hoje pela gestão?",
        "Como são garantidas qualidade, consistência, atualização e governança dos dados?",
        "Quais decisões ainda dependem de planilhas manuais ou análises pontuais?",
        "Quais indicadores deveriam compor uma rotina executiva de inteligência de mercado?",
        "Quais bases de dados são mais críticas para o diagnóstico inicial?",
    ],
    "E-commerce e Omnichannel": [
        "Quais canais digitais existem e como se integram com lojas físicas?",
        "Como são acompanhados pedidos, entrega, retirada, ruptura e experiência digital?",
        "Quais categorias performam melhor ou pior no canal online?",
        "Como estoque, preço e campanhas são sincronizados entre canais?",
        "Quais oportunidades existem para ampliar vendas digitais com rentabilidade?",
    ],
    "Atendimento ao Cliente e CRM": [
        "Como a empresa coleta, classifica e trata reclamações, elogios e sugestões?",
        "Quais indicadores de satisfação, recorrência, fidelização ou NPS são acompanhados?",
        "Como dados de clientes influenciam campanhas, sortimento e atendimento?",
        "Quais problemas recorrentes mais afetam a experiência do consumidor?",
        "Quais ações poderiam melhorar relacionamento e retenção de clientes?",
    ],
    "Expansão e Novos Negócios": [
        "Como são avaliadas oportunidades de novas lojas, regiões ou formatos?",
        "Quais dados são usados para análise de mercado, concorrência e viabilidade?",
        "Como desempenho das lojas atuais orienta decisões de expansão?",
        "Quais riscos precisam ser avaliados antes de novos investimentos?",
        "Quais estudos ou indicadores deveriam apoiar a expansão futura?",
    ],
    "Jurídico e Compliance": [
        "Quais contratos, políticas e riscos legais são mais críticos para a operação?",
        "Como a empresa trata LGPD, confidencialidade, auditorias e compliance interno?",
        "Quais processos exigem maior formalização documental ou controle de risco?",
        "Como jurídico e compliance participam das decisões estratégicas e operacionais?",
        "Quais pontos precisam ser considerados no projeto para reduzir exposição legal?",
    ],
    "Qualidade e Segurança Alimentar": [
        "Como são controladas boas práticas, validade, temperatura, rastreabilidade e manipulação?",
        "Quais categorias perecíveis apresentam maior risco ou perda?",
        "Como são acompanhadas auditorias sanitárias, não conformidades e planos corretivos?",
        "Como qualidade se integra com compras, recebimento, loja e prevenção de perdas?",
        "Quais controles deveriam ser priorizados para reduzir risco sanitário e perda?",
    ],
    "Manutenção e Facilities": [
        "Como são tratados chamados, manutenção preventiva e corretiva?",
        "Quais equipamentos ou instalações geram maior impacto operacional quando falham?",
        "Como custos, SLA, recorrência de falhas e fornecedores são acompanhados?",
        "Como manutenção se integra com operação, loja, CD e segurança alimentar?",
        "Quais ações preventivas poderiam reduzir paradas, perdas e urgências?",
    ],
    "ESG e Sustentabilidade": [
        "Quais práticas ambientais, sociais e de governança já existem na empresa?",
        "Como são tratados resíduos, energia, doações, impacto social e fornecedores?",
        "Quais indicadores ESG são medidos ou poderiam ser implantados?",
        "Quais oportunidades de sustentabilidade também reduzem custo ou risco operacional?",
        "Quais temas ESG são relevantes para reputação, clientes e parceiros?",
    ],
}


PROJECT_STAGE_DEFAULTS = [
    (1, "Onboarding e alinhamento inicial", "Formalização do escopo, responsáveis, ritos de comunicação e objetivos esperados.", "Concluída"),
    (2, "Imersão com áreas-chave", "Entrevistas estruturadas com Operações, Compras, Vendas, Marketing, Logística, Financeiro e Diretoria.", "Em andamento"),
    (3, "Coleta e validação de dados", "Solicitação, recebimento e validação das bases necessárias para o diagnóstico.", "Pendente"),
    (4, "Diagnóstico de maturidade", "Avaliação das práticas atuais e identificação dos principais gaps por área.", "Pendente"),
    (5, "Priorização das oportunidades", "Classificação das oportunidades por impacto, urgência, esforço e aderência estratégica.", "Pendente"),
    (6, "Plano de ação 90 dias", "Desenho do roadmap de ações, responsáveis, prazos, indicadores e entregáveis.", "Pendente"),
    (7, "Execução assistida e ritos", "Acompanhamento das ações priorizadas, reuniões de evolução e ajustes de rota.", "Pendente"),
    (8, "Relatório executivo e continuidade", "Consolidação de resultados, aprendizados, próximos passos e proposta de continuidade.", "Pendente"),
]

QUESTIONNAIRE_DEFAULTS = [
    {
        "title": "Imersão Operacional",
        "context_area": "Operação de loja e logística",
        "target_role": "Gerente de Operações",
        "description": "Panorama da operação, execução em loja, gargalos, perdas, ruptura, produtividade e integração com abastecimento.",
        "questions": [
            "Quais são os principais gargalos operacionais que mais impactam a rotina das lojas hoje?",
            "Como a empresa identifica, acompanha e trata ruptura nas lojas?",
            "Quais indicadores operacionais são acompanhados semanalmente pela liderança?",
            "Quais processos dependem mais de conhecimento informal das equipes do que de padrão documentado?",
            "Quais oportunidades de melhoria poderiam gerar impacto rápido nos próximos 90 dias?",
        ],
    },
    {
        "title": "Imersão de Compras",
        "context_area": "Compras e abastecimento",
        "target_role": "Gerente de Compras",
        "description": "Mapeamento da governança de compras, negociação, fornecedores, calendário comercial, verba, margem e nível de serviço.",
        "questions": [
            "Como é definido o calendário de compras e negociações comerciais?",
            "Quais critérios são usados para priorizar fornecedores, categorias e oportunidades de negociação?",
            "Como compras acompanha ruptura, excesso de estoque e cobertura por categoria?",
            "Quais informações faltam para melhorar a tomada de decisão em compras?",
            "Quais categorias exigem atenção imediata por margem, giro, ruptura ou competitividade?",
        ],
    },
    {
        "title": "Imersão Comercial, Vendas e Marketing",
        "context_area": "Vendas, marketing, pricing e categorias",
        "target_role": "Gerente de Vendas / Marketing",
        "description": "Entendimento das campanhas, pricing, comunicação comercial, mix, posicionamento competitivo e percepção do cliente final.",
        "questions": [
            "Como são definidas as campanhas promocionais e os produtos foco?",
            "A empresa acompanha concorrência, preço, margem e performance por categoria de forma integrada?",
            "Quais canais de comunicação e ações comerciais têm melhor resultado percebido?",
            "Como as áreas comercial, compras e operação se alinham antes e depois das campanhas?",
            "Quais oportunidades de venda ou posicionamento ainda não estão sendo exploradas?",
        ],
    },
    {
        "title": "Imersão Executiva",
        "context_area": "Estratégia e gestão",
        "target_role": "Diretoria Executiva",
        "description": "Visão estratégica da empresa, prioridades, desafios de crescimento, cultura de dados, governança e expectativas com a consultoria.",
        "questions": [
            "Quais são as três prioridades estratégicas da empresa para os próximos 12 meses?",
            "Quais problemas mais afetam margem, crescimento, produtividade ou satisfação dos clientes?",
            "Como a diretoria avalia hoje a qualidade das informações disponíveis para decisão?",
            "Quais decisões críticas ainda são tomadas com pouca evidência ou baixa padronização de dados?",
            "Ao final deste projeto, quais entregas fariam a diretoria considerar a consultoria bem-sucedida?",
        ],
    },
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cnpj TEXT,
    segment TEXT,
    city TEXT,
    state TEXT,
    stores INTEGER DEFAULT 0,
    monthly_revenue REAL DEFAULT 0,
    contact_name TEXT,
    contact_email TEXT,
    status TEXT DEFAULT 'Diagnóstico',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    profile_model TEXT,
    department_area TEXT,
    access_scope TEXT,
    permission_notes TEXT,
    company_id INTEGER,
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY(company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS user_project_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    assigned_at TEXT NOT NULL,
    UNIQUE(user_id, project_id),
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    value REAL DEFAULT 0,
    status TEXT DEFAULT 'Vigente',
    notes TEXT,
    FOREIGN KEY(company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    objective TEXT,
    phase TEXT DEFAULT 'Onboarding',
    progress INTEGER DEFAULT 0,
    start_date TEXT,
    end_date TEXT,
    status TEXT DEFAULT 'Em andamento',
    FOREIGN KEY(company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    owner TEXT,
    responsible_team TEXT DEFAULT 'Atacarejo Insights',
    start_date TEXT,
    due_date TEXT,
    original_due_date TEXT,
    completed_at TEXT,
    extension_reason TEXT,
    status TEXT DEFAULT 'Pendente',
    priority TEXT DEFAULT 'Média',
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS diagnostic_areas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS diagnostic_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    area_id INTEGER NOT NULL,
    score INTEGER DEFAULT 1,
    comment TEXT,
    updated_by INTEGER,
    updated_at TEXT NOT NULL,
    UNIQUE(company_id, area_id),
    FOREIGN KEY(company_id) REFERENCES companies(id),
    FOREIGN KEY(area_id) REFERENCES diagnostic_areas(id),
    FOREIGN KEY(updated_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS diagnostic_questionnaires (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    context_area TEXT,
    target_role TEXT,
    description TEXT,
    status TEXT DEFAULT 'Aberto',
    visible_to_client INTEGER DEFAULT 1,
    created_by INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY(company_id) REFERENCES companies(id),
    FOREIGN KEY(created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS diagnostic_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    questionnaire_id INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    question_type TEXT DEFAULT 'textarea',
    sort_order INTEGER DEFAULT 0,
    FOREIGN KEY(questionnaire_id) REFERENCES diagnostic_questionnaires(id)
);

CREATE TABLE IF NOT EXISTS diagnostic_questionnaire_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    questionnaire_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    answer_text TEXT,
    answered_at TEXT NOT NULL,
    UNIQUE(questionnaire_id, question_id, user_id),
    FOREIGN KEY(questionnaire_id) REFERENCES diagnostic_questionnaires(id),
    FOREIGN KEY(question_id) REFERENCES diagnostic_questions(id),
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS project_stages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    status TEXT DEFAULT 'Pendente',
    start_date TEXT,
    end_date TEXT,
    visible_to_client INTEGER DEFAULT 1,
    updated_at TEXT,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS project_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    author_id INTEGER,
    note TEXT NOT NULL,
    visibility TEXT DEFAULT 'Cliente',
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(author_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS files_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    file_type TEXT,
    status TEXT DEFAULT 'Solicitado',
    notes TEXT,
    due_date TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    cnpj TEXT,
    segment TEXT,
    city TEXT,
    state TEXT,
    stores INTEGER DEFAULT 0,
    monthly_revenue REAL DEFAULT 0,
    contact_name TEXT NOT NULL,
    contact_email TEXT NOT NULL,
    contact_phone TEXT,
    contact_role TEXT,
    interest_area TEXT,
    message TEXT,
    source TEXT DEFAULT 'Site',
    status TEXT DEFAULT 'Novo lead',
    created_at TEXT NOT NULL,
    reviewed_by INTEGER,
    reviewed_at TEXT,
    converted_company_id INTEGER,
    FOREIGN KEY(reviewed_by) REFERENCES users(id),
    FOREIGN KEY(converted_company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS change_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    user_id INTEGER,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    field_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    status TEXT DEFAULT 'Pendente',
    admin_note TEXT,
    created_at TEXT NOT NULL,
    reviewed_by INTEGER,
    reviewed_at TEXT,
    FOREIGN KEY(company_id) REFERENCES companies(id),
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(reviewed_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    entity TEXT,
    entity_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_one(sql, args=()):
    return get_db().execute(sql, args).fetchone()


def query_all(sql, args=()):
    return get_db().execute(sql, args).fetchall()


def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur


def today_iso():
    return date.today().isoformat()


def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_action(action, entity=None, entity_id=None):
    user_id = session.get("user_id")
    try:
        execute(
            "INSERT INTO audit_logs (user_id, action, entity, entity_id, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, action, entity, entity_id, now_iso()),
        )
    except Exception:
        pass


def ensure_area_exists(name, description=None):
    """Cria uma área de diagnóstico/imersão quando ela ainda não estiver mapeada."""
    if not name:
        return None
    clean_name = " ".join(name.strip().split())
    if not clean_name:
        return None
    existing = query_one("SELECT id FROM diagnostic_areas WHERE LOWER(name) = LOWER(?)", (clean_name,))
    if existing:
        return existing["id"]
    cur = execute(
        "INSERT INTO diagnostic_areas (name, description) VALUES (?, ?)",
        (clean_name, description or "Área incluída manualmente para diagnóstico e imersão consultiva."),
    )
    log_action("Área de diagnóstico criada", "diagnostic_areas", cur.lastrowid)
    return cur.lastrowid


def get_area_names():
    return [row["name"] for row in query_all("SELECT name FROM diagnostic_areas ORDER BY name")]


def ensure_columns():
    """Migra bancos locais de versões anteriores sem perder dados."""
    migrations = {
        "users": [
            ("profile_model", "TEXT"),
            ("department_area", "TEXT"),
            ("access_scope", "TEXT"),
            ("permission_notes", "TEXT"),
        ],
        "tasks": [
            ("responsible_team", "TEXT DEFAULT 'Atacarejo Insights'"),
            ("start_date", "TEXT"),
            ("original_due_date", "TEXT"),
            ("completed_at", "TEXT"),
            ("extension_reason", "TEXT"),
        ],
        "leads": [
            ("reviewed_by", "INTEGER"),
            ("reviewed_at", "TEXT"),
            ("converted_company_id", "INTEGER"),
        ],
    }
    for table, columns in migrations.items():
        try:
            existing = {row["name"] for row in query_all(f"PRAGMA table_info({table})")}
        except Exception:
            continue
        for name, definition in columns:
            if name not in existing:
                execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def task_condition(task):
    """Classificação executiva de prazo/status da tarefa."""
    status = task["status"] if isinstance(task, sqlite3.Row) else task.get("status")
    due = task["due_date"] if isinstance(task, sqlite3.Row) else task.get("due_date")
    completed = task["completed_at"] if isinstance(task, sqlite3.Row) else task.get("completed_at")
    today = today_iso()
    if status == "Cancelada":
        return "Cancelada"
    if status == "Prorrogada":
        return "Prorrogada"
    if status == "Concluída":
        if completed and due and completed[:10] <= due:
            return "Concluída no prazo"
        if completed and due and completed[:10] > due:
            return "Concluída com atraso"
        return "Concluída"
    if due and due < today:
        return "Atrasada"
    return status or "Pendente"


def task_condition_class(task):
    label = task_condition(task)
    return {
        "Atrasada": "danger",
        "Prorrogada": "warning",
        "Cancelada": "muted-pill",
        "Concluída no prazo": "done",
        "Concluída com atraso": "warning",
        "Concluída": "done",
    }.get(label, "")


def create_change_request(company_id, entity_type, entity_id, field_name, old_value, new_value):
    old_value = "" if old_value is None else str(old_value)
    new_value = "" if new_value is None else str(new_value)
    if old_value.strip() == new_value.strip():
        return None
    cur = execute(
        """
        INSERT INTO change_requests (company_id, user_id, entity_type, entity_id, field_name, old_value, new_value, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Pendente', ?)
        """,
        (company_id, session.get("user_id"), entity_type, entity_id, field_name, old_value, new_value, now_iso()),
    )
    log_action("Solicitação de alteração criada", "change_requests", cur.lastrowid)
    return cur.lastrowid


def ensure_demo_extensions():
    """Garante dados de demonstração da v10 mesmo quando o banco da v9 já existe."""
    company = query_one("SELECT * FROM companies ORDER BY id LIMIT 1")
    if not company:
        return
    company_id = company["id"]

    demo_users = [
        ("Gerente de Operações Demo", "operacoes@demo.com", "client_collaborator"),
        ("Gerente de Compras Demo", "compras@demo.com", "client_collaborator"),
        ("Gerente de Vendas e Marketing Demo", "vendas@demo.com", "client_collaborator"),
        ("Diretor Executivo Demo", "diretoria@demo.com", "client_admin"),
    ]
    profile_by_email = {
        "operacoes@demo.com": "gestor_area",
        "compras@demo.com": "gestor_area",
        "vendas@demo.com": "gestor_area",
        "diretoria@demo.com": "diretor_executivo",
        "cliente@demo.com": "cliente_master",
        "admin@atacarejoinsights.com": "admin_geral",
    }
    for name, email, role in demo_users:
        exists = query_one("SELECT id FROM users WHERE email = ?", (email,))
        if not exists:
            execute(
                """
                INSERT INTO users (name, email, password_hash, role, profile_model, access_scope, company_id, active, created_at)
                VALUES (?, ?, ?, ?, ?, 'company_only', ?, 1, ?)
                """,
                (name, email, generate_password_hash("cliente123"), role, profile_by_email.get(email), company_id, now_iso()),
            )
    for email, profile in profile_by_email.items():
        execute("UPDATE users SET profile_model = COALESCE(profile_model, ?), access_scope = COALESCE(access_scope, ?) WHERE email = ?", (profile, "company_only" if profile.startswith("cliente") or profile in {"gestor_area", "diretor_executivo"} else "total", email))

    project = query_one("SELECT * FROM projects WHERE company_id = ? ORDER BY id LIMIT 1", (company_id,))
    if project:
        stage_count = query_one("SELECT COUNT(*) AS c FROM project_stages WHERE project_id = ?", (project["id"],))["c"]
        if stage_count == 0:
            for order, title, desc, status in PROJECT_STAGE_DEFAULTS:
                execute(
                    """
                    INSERT INTO project_stages (project_id, title, description, sort_order, status, visible_to_client, updated_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?)
                    """,
                    (project["id"], title, desc, order, status, now_iso()),
                )

    q_count = query_one("SELECT COUNT(*) AS c FROM diagnostic_questionnaires WHERE company_id = ?", (company_id,))["c"]
    if q_count == 0:
        admin = query_one("SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1")
        admin_id = admin["id"] if admin else None
        for qdef in QUESTIONNAIRE_DEFAULTS:
            qcur = execute(
                """
                INSERT INTO diagnostic_questionnaires (company_id, title, context_area, target_role, description, status, visible_to_client, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    company_id,
                    qdef["title"],
                    qdef["context_area"],
                    qdef["target_role"],
                    qdef["description"],
                    "Em coleta",
                    admin_id,
                    now_iso(),
                ),
            )
            qid = qcur.lastrowid
            for idx, question in enumerate(qdef["questions"], start=1):
                execute(
                    """
                    INSERT INTO diagnostic_questions (questionnaire_id, question_text, question_type, sort_order)
                    VALUES (?, ?, 'textarea', ?)
                    """,
                    (qid, question, idx),
                )

        # Respostas simuladas para demonstrar a visualização por respondente.
        sample_map = {
            "Imersão Operacional": "operacoes@demo.com",
            "Imersão de Compras": "compras@demo.com",
            "Imersão Comercial, Vendas e Marketing": "vendas@demo.com",
            "Imersão Executiva": "diretoria@demo.com",
        }
        for title, email in sample_map.items():
            questionnaire = query_one("SELECT id FROM diagnostic_questionnaires WHERE company_id = ? AND title = ?", (company_id, title))
            respondent = query_one("SELECT id FROM users WHERE email = ?", (email,))
            if questionnaire and respondent:
                questions = query_all("SELECT * FROM diagnostic_questions WHERE questionnaire_id = ? ORDER BY sort_order", (questionnaire["id"],))
                for q in questions:
                    execute(
                        """
                        INSERT OR IGNORE INTO diagnostic_questionnaire_answers (questionnaire_id, question_id, user_id, answer_text, answered_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            questionnaire["id"],
                            q["id"],
                            respondent["id"],
                            "Resposta demonstrativa: registrar aqui a visão específica do responsável da área, evidências observadas e principais oportunidades percebidas.",
                            now_iso(),
                        ),
                    )


def get_project_stages(project_id, include_internal=False):
    if include_internal:
        return query_all("SELECT * FROM project_stages WHERE project_id = ? ORDER BY sort_order, id", (project_id,))
    return query_all("SELECT * FROM project_stages WHERE project_id = ? AND visible_to_client = 1 ORDER BY sort_order, id", (project_id,))


def get_company_questionnaires(company_id, include_internal=False):
    visibility_clause = "" if include_internal else "AND q.visible_to_client = 1"
    return query_all(
        f"""
        SELECT q.*, COUNT(DISTINCT a.user_id) AS respondent_count, COUNT(a.id) AS answer_count
        FROM diagnostic_questionnaires q
        LEFT JOIN diagnostic_questionnaire_answers a ON a.questionnaire_id = q.id
        WHERE q.company_id = ? {visibility_clause}
        GROUP BY q.id
        ORDER BY q.created_at DESC, q.id DESC
        """,
        (company_id,),
    )


def init_db():
    db_dir = os.path.dirname(app.config["DATABASE"]) or "."
    os.makedirs(db_dir, exist_ok=True)
    print(f"[Atacarejo Insights] Inicializando banco em: {app.config['DATABASE']}", file=sys.stderr, flush=True)
    with app.app_context():
        db = get_db()
        db.executescript(SCHEMA)
        db.commit()
        ensure_columns()
        for name, desc in AREAS:
            db.execute(
                "INSERT OR IGNORE INTO diagnostic_areas (name, description) VALUES (?, ?)",
                (name, desc),
            )
        db.commit()

        users_count = query_one("SELECT COUNT(*) AS c FROM users")["c"]
        if users_count == 0:
            company_cur = execute(
                """
                INSERT INTO companies (name, cnpj, segment, city, state, stores, monthly_revenue, contact_name, contact_email, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Cliente Demonstração Atacarejo",
                    "00.000.000/0001-00",
                    "Supermercado / Atacarejo",
                    "Recife",
                    "PE",
                    5,
                    1800000,
                    "Diretoria Comercial",
                    "cliente@demo.com",
                    "Diagnóstico",
                    now_iso(),
                ),
            )
            company_id = company_cur.lastrowid

            execute(
                """
                INSERT INTO users (name, email, password_hash, role, company_id, active, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    "Administrador Atacarejo Insights",
                    "admin@atacarejoinsights.com",
                    generate_password_hash("admin123"),
                    "admin",
                    None,
                    now_iso(),
                ),
            )
            execute(
                """
                INSERT INTO users (name, email, password_hash, role, company_id, active, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    "Cliente Demonstração",
                    "cliente@demo.com",
                    generate_password_hash("cliente123"),
                    "client_admin",
                    company_id,
                    now_iso(),
                ),
            )
            execute(
                """
                INSERT INTO contracts (company_id, title, start_date, end_date, value, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    company_id,
                    "Projeto inicial de 90 dias",
                    today_iso(),
                    "2026-08-31",
                    15000,
                    "Vigente",
                    "Pagamento condicionado à satisfação do cliente e possibilidade de contrato de continuidade por 12 meses.",
                ),
            )
            project_cur = execute(
                """
                INSERT INTO projects (company_id, name, objective, phase, progress, start_date, end_date, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    company_id,
                    "Diagnóstico e estruturação de inteligência de mercado",
                    "Entender a estrutura atual, identificar oportunidades críticas e implantar uma rotina inicial de gestão por dados.",
                    "Diagnóstico inicial",
                    35,
                    today_iso(),
                    "2026-08-31",
                    "Em andamento",
                ),
            )
            project_id = project_cur.lastrowid
            seed_tasks = [
                ("Realizar reunião de onboarding", "Atacarejo Insights", "2026-06-03", "Concluída", "Alta"),
                ("Responder questionário de diagnóstico", "Cliente", "2026-06-07", "Em andamento", "Alta"),
                ("Enviar base de vendas dos últimos 6 meses", "Cliente", "2026-06-10", "Pendente", "Alta"),
                ("Mapear rotina atual de compras", "Atacarejo Insights", "2026-06-15", "Pendente", "Média"),
                ("Construir matriz de maturidade inicial", "Atacarejo Insights", "2026-06-20", "Pendente", "Média"),
            ]
            for title, owner, due, status, priority in seed_tasks:
                execute(
                    """
                    INSERT INTO tasks (project_id, title, description, owner, due_date, status, priority, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (project_id, title, "", owner, due, status, priority, now_iso()),
                )
            for file_title in [
                "Base de vendas por SKU",
                "Cadastro de produtos",
                "Relatório de ruptura",
                "Tabela de fornecedores",
                "Histórico de compras",
            ]:
                execute(
                    """
                    INSERT INTO files_registry (company_id, title, file_type, status, notes, due_date, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (company_id, file_title, "Planilha", "Solicitado", "Documento necessário para diagnóstico inicial.", "2026-06-10", now_iso()),
                )
            # baseline diagnostic answers
            area_rows = query_all("SELECT id FROM diagnostic_areas ORDER BY id")
            scores = [3, 2, 3, 2, 2, 3, 1]
            for row, score in zip(area_rows, scores):
                execute(
                    """
                    INSERT INTO diagnostic_answers (company_id, area_id, score, comment, updated_by, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (company_id, row["id"], score, "Pontuação inicial simulada para demonstração.", 1, now_iso()),
                )

        ensure_demo_extensions()


@app.before_request
def load_logged_in_user():
    # Proteção extra para ambiente publicado: se o navegador estiver com cookie antigo
    # ou se o banco local precisar ser recriado, a página pública não deve cair em erro 500.
    user_id = session.get("user_id")
    g.user = None
    if user_id is not None:
        try:
            g.user = query_one("SELECT * FROM users WHERE id = ? AND active = 1", (user_id,))
            if g.user is None:
                session.clear()
        except Exception:
            traceback.print_exc(file=sys.stderr)
            session.clear()
            g.user = None




@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route("/service-worker.js")
def service_worker_kill():
    script = """self.addEventListener('install', function(e){ self.skipWaiting(); });
self.addEventListener('activate', function(e){ e.waitUntil(self.registration.unregister().then(function(){ return self.clients.matchAll(); }).then(function(clients){ clients.forEach(function(client){ client.navigate(client.url); }); })); });
"""
    return app.response_class(script, mimetype="application/javascript", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"})


@app.context_processor
def inject_helpers():
    return {
        "role_labels": {
            "admin": "Administrador",
            "consultant": "Consultor",
            "client_admin": "Cliente administrador",
            "client_collaborator": "Cliente colaborador",
            "client_viewer": "Cliente visualizador",
        },
        "is_admin": lambda: g.user and g.user["role"] in ADMIN_ROLES,
        "current_year": date.today().year,
        "task_condition": task_condition,
        "task_condition_class": task_condition_class,
        "profile_templates": PROFILE_TEMPLATES,
        "internal_profile_templates": INTERNAL_PROFILE_TEMPLATES,
        "client_profile_templates": CLIENT_PROFILE_TEMPLATES,
        "access_levels": ACCESS_LEVELS,
        "profile_label": profile_label,
    }


def redirect_for_user(user):
    """Direciona cada usuário para o ambiente correto de acordo com perfil e permissão."""
    if user["role"] in ADMIN_ROLES:
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("client_dashboard"))


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        return view(**kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        if g.user["role"] not in ADMIN_ROLES:
            abort(403)
        return view(**kwargs)

    return wrapped_view


def can_access_company(company_id):
    if g.user is None:
        return False
    if g.user["role"] in ADMIN_ROLES:
        return True
    return g.user["company_id"] == int(company_id)


def require_company_access(company_id):
    if not can_access_company(company_id):
        abort(403)




def get_client_about_content():
    """Conteúdo institucional exibido no portal do cliente."""
    return {
        "pillars": [
            {
                "title": "Diagnosticar com profundidade",
                "text": "Mapeamos processos, dados, ritos de gestão e gargalos operacionais para separar percepção de evidência e localizar onde o resultado está sendo perdido.",
            },
            {
                "title": "Estruturar decisões inteligentes",
                "text": "Organizamos indicadores, prioridades, responsáveis e planos de ação para transformar dados dispersos em uma rotina de gestão mais segura e previsível.",
            },
            {
                "title": "Acompanhar a execução",
                "text": "Ajudamos a empresa a monitorar etapas, prazos, entregas e indicadores, mantendo clareza sobre o que já foi concluído e o que ainda precisa avançar.",
            },
            {
                "title": "Gerar competitividade sustentável",
                "text": "O foco não é apenas criar relatórios, mas apoiar decisões que melhorem disponibilidade, margem, produtividade, sortimento, compras, abastecimento e experiência do cliente.",
            },
        ],
        "insights": [
            {
                "title": "O varejo alimentar é grande demais para ser gerido apenas por intuição",
                "text": "O setor supermercadista brasileiro movimenta mais de R$ 1 trilhão por ano e representa uma fatia relevante da economia. Nesse ambiente, pequenos ganhos de eficiência em margem, estoque, ruptura e produtividade podem gerar impactos expressivos.",
                "source": "Referência: Ranking ABRAS 2025",
            },
            {
                "title": "Margens pressionadas exigem gestão mais analítica",
                "text": "Relatórios internacionais de varejo mostram um cenário de crescimento mais seletivo, consumidores atentos a valor e custos operacionais pressionando o resultado. A resposta passa por processos mais integrados, leitura de dados e execução disciplinada.",
                "source": "Referências: McKinsey State of Grocery, Deloitte Global Powers of Retailing e FMI Grocery Shopper Trends",
            },
            {
                "title": "Dados, omnicanalidade e eficiência deixaram de ser diferenciais isolados",
                "text": "Grandes redes globais vêm combinando lojas físicas, canais digitais, automação, marcas próprias, supply chain inteligente e personalização para continuar crescendo em mercados competitivos.",
                "source": "Referências: Walmart, NIQ, Deloitte e estudos setoriais de varejo",
            },
        ],
        "cases": [
            {
                "company": "Walmart",
                "strategy": "Estratégia omnicanal apoiada por tecnologia, escala, dados, automação e integração entre loja física, e-commerce e supply chain.",
                "lesson": "Crescimento sustentável exige conectar operação, tecnologia e execução comercial em uma arquitetura única de gestão.",
            },
            {
                "company": "Assaí Atacadista",
                "strategy": "Expansão, foco operacional, modelo de atacarejo e busca contínua por eficiência em lojas, sortimento e produtividade.",
                "lesson": "Clareza de modelo de negócio, disciplina de expansão e gestão operacional consistente ajudam a transformar escala em vantagem competitiva.",
            },
            {
                "company": "Redes globais de grocery e supermercados",
                "strategy": "Aceleração de marcas próprias, formatos de loja mais adaptáveis, leitura granular do consumidor e melhoria de disponibilidade.",
                "lesson": "A reinvenção do varejo passa por entender melhor o cliente, revisar o sortimento e tomar decisões com base em evidências, não apenas em histórico ou costume.",
            },
        ],
        "method_steps": [
            "Imersão com gestores e áreas-chave",
            "Levantamento de dados, processos e indicadores",
            "Diagnóstico de maturidade e riscos críticos",
            "Priorização de oportunidades por impacto e viabilidade",
            "Plano de ação com responsáveis, prazos e entregas",
            "Acompanhamento da jornada até o fechamento do ciclo",
        ],
        "references": [
            "ABRAS — Ranking ABRAS 2025 e dados do setor supermercadista brasileiro",
            "McKinsey & Company — State of Grocery Retail e estudos de tendências de varejo alimentar",
            "Deloitte — Global Powers of Retailing 2025",
            "NIQ — estudos sobre comportamento do consumidor, grocery trends e marcas próprias",
            "FMI — U.S. Grocery Shopper Trends",
            "Relatórios corporativos e comunicados estratégicos de grandes redes globais de varejo alimentar",
        ],
    }

def get_project_with_company(project_id):
    project = query_one(
        """
        SELECT p.*, c.name AS company_name, c.id AS company_id
        FROM projects p
        JOIN companies c ON c.id = p.company_id
        WHERE p.id = ?
        """,
        (project_id,),
    )
    if not project:
        abort(404)
    require_company_access(project["company_id"])
    return project


def inline_public_home():
    """Landing page pública independente de template.
    Usada como fallback no Render caso a pasta templates não tenha sido enviada.
    """
    return """
    <!doctype html>
    <html lang="pt-BR">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Atacarejo Insights</title>
      <style>
        :root{--roxo:#6813e8;--laranja:#ff9f1c;--bg:#06020b;--card:#140f1f;--txt:#f7f3ff;--muted:#c8bed9;}
        *{box-sizing:border-box} body{margin:0;background:radial-gradient(circle at 78% 0%,rgba(104,19,232,.35),transparent 30%),linear-gradient(135deg,#050108,#10091a 55%,#1b0837);color:var(--txt);font-family:Arial,Helvetica,sans-serif;}
        a{color:inherit}.wrap{max-width:1160px;margin:auto;padding:28px}.nav{display:flex;justify-content:space-between;align-items:center;gap:16px}.brand{font-weight:800;letter-spacing:.04em}.pill{display:inline-block;background:linear-gradient(90deg,var(--roxo),var(--laranja));padding:9px 14px;border-radius:999px;font-weight:800}.btn{display:inline-block;text-decoration:none;border:1px solid rgba(255,255,255,.16);padding:13px 18px;border-radius:14px;font-weight:800;background:rgba(255,255,255,.06)}.btn.primary{background:linear-gradient(90deg,var(--roxo),var(--laranja));border:0}.hero{display:grid;grid-template-columns:1.15fr .85fr;gap:28px;align-items:center;min-height:74vh}.hero h1{font-size:clamp(38px,6vw,76px);line-height:.98;margin:18px 0}.hero p{font-size:19px;color:var(--muted);line-height:1.55}.card{background:rgba(20,15,31,.82);border:1px solid rgba(255,255,255,.12);border-radius:28px;padding:26px;box-shadow:0 24px 80px rgba(0,0,0,.35)}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin:24px 0}.mini{background:rgba(255,255,255,.055);border:1px solid rgba(255,255,255,.1);border-radius:20px;padding:20px}.mini h3{margin:0 0 10px}.mini p{font-size:15px;margin:0;color:var(--muted)}.cta{display:flex;gap:12px;flex-wrap:wrap;margin-top:28px}.note{font-size:13px;color:#b9aeca;margin-top:14px}@media(max-width:820px){.hero,.grid{grid-template-columns:1fr}.nav{align-items:flex-start;flex-direction:column}.wrap{padding:20px}.hero{min-height:auto;padding-top:34px}}
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="nav">
          <div class="brand">Atacarejo <span style="color:#8b4cff">Insights</span></div>
          <div class="cta" style="margin:0"><a class="btn" href="/login">Acessar portal</a><a class="btn primary" href="/cadastro">Cadastrar interesse</a></div>
        </div>
        <section class="hero">
          <div>
            <span class="pill">Inteligência aplicada ao varejo alimentar</span>
            <h1>Planejamento, dados e execução para negócios mais fortes.</h1>
            <p>A Atacarejo Insights apoia supermercados, atacarejos e operações de varejo alimentar na estruturação de diagnósticos, planos de ação e rotinas de gestão para aumentar segurança, competitividade e capacidade de crescimento.</p>
            <div class="cta"><a class="btn primary" href="/cadastro">Quero receber contato</a><a class="btn" href="/login">Já sou cliente</a></div>
            <div class="note">Primeiro cadastro simplificado. Os dados completos são tratados depois, em reunião com nossa equipe.</div>
          </div>
          <div class="card">
            <h2>Como podemos ajudar</h2>
            <div class="grid" style="grid-template-columns:1fr">
              <div class="mini"><h3>Diagnóstico empresarial</h3><p>Mapeamento de áreas críticas, maturidade de gestão, processos e oportunidades de melhoria.</p></div>
              <div class="mini"><h3>Estruturação do projeto</h3><p>Transformação do diagnóstico em plano de ação com responsáveis, prazos, etapas e acompanhamento.</p></div>
              <div class="mini"><h3>Gestão orientada por dados</h3><p>Indicadores, rotinas e decisões mais consistentes para reduzir riscos e melhorar performance.</p></div>
            </div>
          </div>
        </section>
        <section class="grid">
          <div class="mini"><h3>Compras e abastecimento</h3><p>Melhor conexão entre demanda, negociação, estoque, sortimento e disponibilidade.</p></div>
          <div class="mini"><h3>Operação e logística</h3><p>Visão integrada da execução em loja, CD, distribuição, perdas e produtividade.</p></div>
          <div class="mini"><h3>Governança do projeto</h3><p>Jornada clara, aprovações, tarefas, documentos e transparência para o cliente contratado.</p></div>
        </section>
      </div>
    </body>
    </html>
    """


def inline_lead_register(success=False):
    msg = "<div class='success'>Cadastro recebido. Nossa equipe entrará em contato.</div>" if success else ""
    return f"""
    <!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Cadastro de interesse - Atacarejo Insights</title>
    <style>body{{margin:0;background:#07030c;color:#fff;font-family:Arial;padding:24px}}.box{{max-width:720px;margin:40px auto;background:#151020;border:1px solid #2c2140;border-radius:24px;padding:28px}}label{{display:block;margin:14px 0 6px}}input{{width:100%;padding:13px;border-radius:12px;border:1px solid #3a2b54;background:#0b0711;color:#fff}}button,.btn{{display:inline-block;margin-top:18px;padding:13px 18px;border:0;border-radius:14px;background:linear-gradient(90deg,#6813e8,#ff9f1c);color:#fff;font-weight:800;text-decoration:none}}.success{{padding:14px;border-radius:12px;background:#123d27;color:#a7f3d0;margin-bottom:14px}}</style></head><body><div class="box"><h1>Cadastro de interesse</h1><p>Informe apenas os dados iniciais. Os detalhes completos serão tratados em reunião com nossa equipe.</p>{msg}<form method="post"><label>Nome do solicitante</label><input name="contact_name" required><label>Nome da empresa</label><input name="company_name" required><label>Estado da matriz</label><input name="state" maxlength="2" placeholder="PE" required><label>Telefone/WhatsApp</label><input name="contact_phone" required><label>E-mail para contato</label><input name="contact_email" type="email" required><button type="submit">Enviar cadastro</button> <a class="btn" href="/">Voltar</a></form></div></body></html>
    """


def inline_login():
    return """
    <!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Login - Atacarejo Insights</title>
    <style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:radial-gradient(circle at 80% 0%,rgba(104,19,232,.35),transparent 30%),#07030c;color:#fff;font-family:Arial}.box{width:min(460px,92vw);background:#151020;border:1px solid #2c2140;border-radius:24px;padding:30px}label{display:block;margin:14px 0 6px}input{width:100%;padding:13px;border-radius:12px;border:1px solid #3a2b54;background:#0b0711;color:#fff}button,.btn{display:inline-block;margin-top:18px;padding:13px 18px;border:0;border-radius:14px;background:linear-gradient(90deg,#6813e8,#ff9f1c);color:#fff;font-weight:800;text-decoration:none}.muted{color:#c8bed9;font-size:14px}</style></head><body><div class="box"><h1>Acessar portal</h1><p class="muted">Entre com o usuário liberado pela Atacarejo Insights.</p><form method="post"><label>E-mail</label><input name="email" type="email" required><label>Senha</label><input name="password" type="password" required><button type="submit">Entrar</button> <a class="btn" href="/">Voltar</a></form><p class="muted">Admin: admin@atacarejoinsights.com / admin123<br>Cliente: cliente@demo.com / cliente123</p></div></body></html>
    """


def render_or_fallback(template_name, fallback_func, **context):
    try:
        return render_template(template_name, **context)
    except TemplateNotFound as exc:
        print(f"[Atacarejo Insights] Template ausente no Render: {exc}", file=sys.stderr)
        return fallback_func()


@app.route("/")
def index():
    # A página inicial pública deve ser sempre o primeiro contato, mesmo que exista cookie antigo.
    # Depois do login, o usuário é direcionado ao ambiente permitido.
    return render_or_fallback("public_home.html", inline_public_home, content=get_client_about_content())


@app.route("/portal")
@login_required
def portal_redirect():
    return redirect_for_user(g.user)


@app.route("/limpar-sessao")
def clear_session_public():
    session.clear()
    flash("Sessão local limpa. Acesse novamente pelo login.", "success")
    return redirect(url_for("index"))


@app.route("/cadastro", methods=("GET", "POST"))
def public_register():
    if request.method == "POST":
        company_name = request.form.get("company_name", "").strip()
        contact_name = request.form.get("contact_name", "").strip()
        contact_email = request.form.get("contact_email", "").strip().lower()
        contact_phone = request.form.get("contact_phone", "").strip()
        state = request.form.get("state", "").strip().upper()
        if not company_name or not contact_name or not contact_email or not contact_phone or not state:
            flash("Informe nome do solicitante, empresa, estado da matriz, telefone e e-mail para concluir o cadastro.", "error")
        else:
            execute(
                """
                INSERT INTO leads (company_name, cnpj, segment, city, state, stores, monthly_revenue, contact_name, contact_email, contact_phone, contact_role, interest_area, message, source, status, created_at)
                VALUES (?, '', '', '', ?, 0, 0, ?, ?, ?, '', 'Primeiro contato', '', 'Site', 'Novo lead', ?)
                """,
                (
                    company_name,
                    state,
                    contact_name,
                    contact_email,
                    contact_phone,
                    now_iso(),
                ),
            )
            flash("Cadastro recebido. Nossa equipe entrará em contato para uma primeira conversa e apresentação da Atacarejo Insights.", "success")
            return redirect(url_for("public_register_success"))
    return render_or_fallback("lead_register.html", lambda: inline_lead_register(False))


@app.route("/cadastro/recebido")
def public_register_success():
    return render_or_fallback("lead_register.html", lambda: inline_lead_register(True), success=True)


@app.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = query_one("SELECT * FROM users WHERE email = ? AND active = 1", (email,))
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("E-mail ou senha inválidos.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            log_action("Login realizado", "users", user["id"])
            return redirect_for_user(user)
    return render_or_fallback("login.html", inline_login)


@app.route("/logout")
def logout():
    log_action("Logout realizado", "users", session.get("user_id"))
    session.clear()
    return redirect(url_for("index"))


@app.route("/admin/dashboard")
@login_required
@admin_required
def admin_dashboard():
    metrics = {
        "clients": query_one("SELECT COUNT(*) AS c FROM companies")["c"],
        "active_projects": query_one("SELECT COUNT(*) AS c FROM projects WHERE status != 'Finalizado'")["c"],
        "open_tasks": query_one("SELECT COUNT(*) AS c FROM tasks WHERE status != 'Concluída'")["c"],
        "revenue": query_one("SELECT COALESCE(SUM(value), 0) AS total FROM contracts WHERE status = 'Vigente'")["total"],
        "avg_maturity": query_one("SELECT COALESCE(AVG(score), 0) AS avg_score FROM diagnostic_answers")["avg_score"],
        "pending_leads": query_one("SELECT COUNT(*) AS c FROM leads WHERE status IN ('Novo lead', 'Contato realizado', 'Reunião marcada', 'Projeto apresentado', 'Em negociação')")["c"],
        "pending_approvals": query_one("SELECT COUNT(*) AS c FROM change_requests WHERE status = 'Pendente'")["c"],
    }
    companies = query_all(
        """
        SELECT c.*, 
               COUNT(DISTINCT p.id) AS projects_count,
               COALESCE(AVG(da.score), 0) AS maturity
        FROM companies c
        LEFT JOIN projects p ON p.company_id = c.id
        LEFT JOIN diagnostic_answers da ON da.company_id = c.id
        GROUP BY c.id
        ORDER BY c.created_at DESC
        """
    )
    pipeline = query_all(
        """
        SELECT phase, COUNT(*) AS total, ROUND(AVG(progress), 0) AS avg_progress
        FROM projects
        GROUP BY phase
        ORDER BY total DESC
        """
    )
    overdue = query_all(
        """
        SELECT t.*, p.name AS project_name, c.name AS company_name
        FROM tasks t
        JOIN projects p ON p.id = t.project_id
        JOIN companies c ON c.id = p.company_id
        WHERE t.status NOT IN ('Concluída', 'Cancelada') AND t.due_date < ?
        ORDER BY t.due_date ASC
        LIMIT 6
        """,
        (today_iso(),),
    )
    return render_template("admin_dashboard.html", metrics=metrics, companies=companies, pipeline=pipeline, overdue=overdue)


@app.route("/client/dashboard")
@login_required
def client_dashboard():
    if g.user["role"] in ADMIN_ROLES:
        return redirect(url_for("admin_dashboard"))
    company_id = g.user["company_id"]
    company = query_one("SELECT * FROM companies WHERE id = ?", (company_id,))
    projects = query_all("SELECT * FROM projects WHERE company_id = ? ORDER BY id DESC", (company_id,))
    tasks = query_all(
        """
        SELECT t.*, p.name AS project_name
        FROM tasks t
        JOIN projects p ON p.id = t.project_id
        WHERE p.company_id = ?
        ORDER BY CASE t.status WHEN 'Pendente' THEN 1 WHEN 'Em andamento' THEN 2 ELSE 3 END, t.due_date ASC
        """,
        (company_id,),
    )
    maturity = query_all(
        """
        SELECT a.name, a.description, COALESCE(d.score, 0) AS score, d.comment
        FROM diagnostic_areas a
        LEFT JOIN diagnostic_answers d ON d.area_id = a.id AND d.company_id = ?
        ORDER BY a.id
        """,
        (company_id,),
    )
    files = query_all("SELECT * FROM files_registry WHERE company_id = ? ORDER BY due_date ASC", (company_id,))
    project_stages = query_all(
        """
        SELECT s.*, p.name AS project_name
        FROM project_stages s
        JOIN projects p ON p.id = s.project_id
        WHERE p.company_id = ? AND s.visible_to_client = 1
        ORDER BY p.id DESC, s.sort_order, s.id
        """,
        (company_id,),
    )
    questionnaires = get_company_questionnaires(company_id, include_internal=False)
    pending_changes = query_all(
        """
        SELECT cr.*, u.name AS user_name
        FROM change_requests cr
        LEFT JOIN users u ON u.id = cr.user_id
        WHERE cr.company_id = ? AND cr.status = 'Pendente'
        ORDER BY cr.created_at DESC
        LIMIT 8
        """,
        (company_id,),
    )
    return render_template("client_dashboard.html", company=company, projects=projects, tasks=tasks, maturity=maturity, files=files, project_stages=project_stages, questionnaires=questionnaires, pending_changes=pending_changes)



@app.route("/client/sobre")
@login_required
def client_about():
    if g.user["role"] in ADMIN_ROLES:
        return redirect(url_for("admin_dashboard"))
    company_id = g.user["company_id"]
    company = query_one("SELECT * FROM companies WHERE id = ?", (company_id,))
    if not company:
        abort(404)
    content = get_client_about_content()
    return redirect(url_for("index"))

@app.route("/client/dados-cadastrais", methods=("GET", "POST"))
@login_required
def client_company_edit():
    if g.user["role"] in ADMIN_ROLES:
        return redirect(url_for("admin_dashboard"))
    if g.user["role"] == "client_viewer":
        abort(403)
    company_id = g.user["company_id"]
    company = query_one("SELECT * FROM companies WHERE id = ?", (company_id,))
    if not company:
        abort(404)
    fields = ["name", "cnpj", "segment", "city", "state", "stores", "monthly_revenue", "contact_name", "contact_email"]
    if request.method == "POST":
        created = 0
        for field in fields:
            new_value = request.form.get(field, "")
            if field in {"stores"}:
                new_value = str(int(new_value or 0))
            if field in {"monthly_revenue"}:
                new_value = str(float(new_value or 0))
            if create_change_request(company_id, "company_profile", company_id, field, company[field], new_value):
                created += 1
        if created:
            flash(f"{created} alteração(ões) enviada(s) para aprovação da Atacarejo Insights.", "success")
        else:
            flash("Nenhuma alteração identificada.", "error")
        return redirect(url_for("client_company_edit"))
    pending = query_all(
        """
        SELECT cr.*, u.name AS user_name
        FROM change_requests cr
        LEFT JOIN users u ON u.id = cr.user_id
        WHERE cr.company_id = ? AND cr.entity_type = 'company_profile'
        ORDER BY cr.created_at DESC
        """,
        (company_id,),
    )
    return render_template("client_company_edit.html", company=company, pending=pending)


@app.route("/admin/leads", methods=("GET", "POST"))
@login_required
@admin_required
def admin_leads():
    if request.method == "POST":
        lead_id = int(request.form.get("lead_id"))
        status = request.form.get("status") or "Em análise"
        execute("UPDATE leads SET status = ?, reviewed_by = ?, reviewed_at = ? WHERE id = ?", (status, g.user["id"], now_iso(), lead_id))
        flash("Status do lead atualizado.", "success")
        return redirect(url_for("admin_leads"))
    leads = query_all("SELECT * FROM leads ORDER BY created_at DESC")
    return render_template("admin_leads.html", leads=leads)


@app.route("/admin/leads/<int:lead_id>/convert", methods=("POST",))
@login_required
@admin_required
def admin_lead_convert(lead_id):
    lead = query_one("SELECT * FROM leads WHERE id = ?", (lead_id,))
    if not lead:
        abort(404)
    password = request.form.get("password") or "cliente123"
    company_cur = execute(
        """
        INSERT INTO companies (name, cnpj, segment, city, state, stores, monthly_revenue, contact_name, contact_email, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Contrato em implantação', ?)
        """,
        (lead["company_name"], lead["cnpj"], lead["segment"], lead["city"], lead["state"], lead["stores"] or 0, lead["monthly_revenue"] or 0, lead["contact_name"], lead["contact_email"], now_iso()),
    )
    company_id = company_cur.lastrowid
    try:
        execute(
            """
            INSERT INTO users (name, email, password_hash, role, profile_model, access_scope, company_id, active, created_at)
            VALUES (?, ?, ?, 'client_admin', 'cliente_master', 'company_only', ?, 1, ?)
            """,
            (lead["contact_name"], lead["contact_email"].strip().lower(), generate_password_hash(password), company_id, now_iso()),
        )
    except sqlite3.IntegrityError:
        flash("Cliente criado, mas já existia usuário com esse e-mail. Revise os usuários manualmente.", "error")
    pcur = execute(
        """
        INSERT INTO projects (company_id, name, objective, phase, progress, start_date, end_date, status)
        VALUES (?, 'Projeto de diagnóstico e estruturação inicial', 'Diagnosticar maturidade, estruturar prioridades e acompanhar plano de ação consultivo.', 'Onboarding e alinhamento inicial', 0, ?, ?, 'Em andamento')
        """,
        (company_id, today_iso(), None),
    )
    project_id = pcur.lastrowid
    for order, title, desc, status in PROJECT_STAGE_DEFAULTS:
        execute(
            """
            INSERT INTO project_stages (project_id, title, description, sort_order, status, visible_to_client, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            (project_id, title, desc, order, 'Pendente' if order > 1 else 'Em andamento', now_iso()),
        )
    execute("UPDATE leads SET status = 'Convertido em cliente', reviewed_by = ?, reviewed_at = ?, converted_company_id = ? WHERE id = ?", (g.user["id"], now_iso(), company_id, lead_id))
    log_action("Lead convertido em cliente", "leads", lead_id)
    flash(f"Lead convertido em cliente. Login definitivo: {lead['contact_email']} / senha inicial: {password}", "success")
    return redirect(url_for("company_detail", company_id=company_id))


@app.route("/admin/aprovacoes", methods=("GET",))
@login_required
@admin_required
def admin_approvals():
    pending = query_all(
        """
        SELECT cr.*, c.name AS company_name, u.name AS user_name, u.email AS user_email
        FROM change_requests cr
        JOIN companies c ON c.id = cr.company_id
        LEFT JOIN users u ON u.id = cr.user_id
        WHERE cr.status = 'Pendente'
        ORDER BY cr.created_at ASC
        """
    )
    reviewed = query_all(
        """
        SELECT cr.*, c.name AS company_name, u.name AS user_name
        FROM change_requests cr
        JOIN companies c ON c.id = cr.company_id
        LEFT JOIN users u ON u.id = cr.user_id
        WHERE cr.status != 'Pendente'
        ORDER BY cr.reviewed_at DESC
        LIMIT 20
        """
    )
    return render_template("admin_approvals.html", pending=pending, reviewed=reviewed)


@app.route("/admin/aprovacoes/<int:request_id>/<action>", methods=("POST",))
@login_required
@admin_required
def admin_approval_action(request_id, action):
    cr = query_one("SELECT * FROM change_requests WHERE id = ?", (request_id,))
    if not cr:
        abort(404)
    if cr["status"] != "Pendente":
        flash("Esta solicitação já foi revisada.", "error")
        return redirect(url_for("admin_approvals"))
    note = request.form.get("admin_note")
    if action == "approve":
        if cr["entity_type"] == "company_profile":
            allowed = {"name", "cnpj", "segment", "city", "state", "stores", "monthly_revenue", "contact_name", "contact_email"}
            if cr["field_name"] not in allowed:
                abort(400)
            execute(f"UPDATE companies SET {cr['field_name']} = ? WHERE id = ?", (cr["new_value"], cr["entity_id"]))
        elif cr["entity_type"] == "questionnaire_answer":
            execute("UPDATE diagnostic_questionnaire_answers SET answer_text = ?, answered_at = ? WHERE id = ?", (cr["new_value"], now_iso(), cr["entity_id"]))
        elif cr["entity_type"] == "file_registry_new":
            payload = json.loads(cr["new_value"] or "{}")
            execute(
                """
                INSERT INTO files_registry (company_id, title, file_type, status, notes, due_date, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (cr["company_id"], payload.get("title"), payload.get("file_type"), payload.get("status") or "Enviado pelo cliente", payload.get("notes"), payload.get("due_date"), now_iso()),
            )
        elif cr["entity_type"] == "user_create":
            payload = json.loads(cr["new_value"] or "{}")
            email = (payload.get("email") or "").strip().lower()
            existing = query_one("SELECT id FROM users WHERE email = ?", (email,))
            if existing:
                flash("Já existe um usuário com esse e-mail. A solicitação não foi aplicada.", "error")
                return redirect(url_for("admin_approvals"))
            profile_model = payload.get("profile_model") or "colaborador_respondente"
            role = profile_to_role(profile_model, "client_collaborator")
            execute(
                """
                INSERT INTO users (name, email, password_hash, role, profile_model, department_area, access_scope, permission_notes, company_id, active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    payload.get("name"),
                    email,
                    generate_password_hash(payload.get("password") or "cliente123"),
                    role,
                    profile_model,
                    payload.get("department_area"),
                    payload.get("access_scope") or "company_only",
                    payload.get("permission_notes"),
                    cr["company_id"],
                    now_iso(),
                ),
            )
        else:
            abort(400)
        execute("UPDATE change_requests SET status = 'Aprovada', admin_note = ?, reviewed_by = ?, reviewed_at = ? WHERE id = ?", (note, g.user["id"], now_iso(), request_id))
        flash("Alteração aprovada e aplicada.", "success")
    elif action == "reject":
        execute("UPDATE change_requests SET status = 'Rejeitada', admin_note = ?, reviewed_by = ?, reviewed_at = ? WHERE id = ?", (note, g.user["id"], now_iso(), request_id))
        flash("Alteração rejeitada.", "success")
    else:
        abort(404)
    log_action(f"Solicitação de alteração {action}", "change_requests", request_id)
    return redirect(url_for("admin_approvals"))


@app.route("/admin/clients")
@login_required
@admin_required
def clients():
    rows = query_all("SELECT * FROM companies ORDER BY name")
    return render_template("clients.html", companies=rows)


@app.route("/admin/clients/new", methods=("GET", "POST"))
@login_required
@admin_required
def client_new():
    if request.method == "POST":
        cur = execute(
            """
            INSERT INTO companies (name, cnpj, segment, city, state, stores, monthly_revenue, contact_name, contact_email, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.form.get("name"),
                request.form.get("cnpj"),
                request.form.get("segment"),
                request.form.get("city"),
                request.form.get("state"),
                int(request.form.get("stores") or 0),
                float(request.form.get("monthly_revenue") or 0),
                request.form.get("contact_name"),
                request.form.get("contact_email"),
                request.form.get("status") or "Diagnóstico",
                now_iso(),
            ),
        )
        company_id = cur.lastrowid
        log_action("Cliente criado", "companies", company_id)
        flash("Cliente cadastrado com sucesso.", "success")
        return redirect(url_for("company_detail", company_id=company_id))
    return render_template("client_form.html")


@app.route("/company/<int:company_id>")
@login_required
def company_detail(company_id):
    require_company_access(company_id)
    company = query_one("SELECT * FROM companies WHERE id = ?", (company_id,))
    if not company:
        abort(404)
    contracts = query_all("SELECT * FROM contracts WHERE company_id = ? ORDER BY id DESC", (company_id,))
    projects = query_all("SELECT * FROM projects WHERE company_id = ? ORDER BY id DESC", (company_id,))
    maturity = query_all(
        """
        SELECT a.name, a.description, COALESCE(d.score, 0) AS score, d.comment
        FROM diagnostic_areas a
        LEFT JOIN diagnostic_answers d ON d.area_id = a.id AND d.company_id = ?
        ORDER BY a.id
        """,
        (company_id,),
    )
    files = query_all("SELECT * FROM files_registry WHERE company_id = ? ORDER BY due_date ASC", (company_id,))
    users = query_all("SELECT id, name, email, role, active FROM users WHERE company_id = ? ORDER BY name", (company_id,))
    questionnaires = get_company_questionnaires(company_id, include_internal=(g.user["role"] in ADMIN_ROLES))
    area_options = query_all("SELECT * FROM diagnostic_areas ORDER BY name")
    pending_changes = query_all(
        """
        SELECT cr.*, u.name AS user_name
        FROM change_requests cr
        LEFT JOIN users u ON u.id = cr.user_id
        WHERE cr.company_id = ? AND cr.status = 'Pendente'
        ORDER BY cr.created_at DESC
        """,
        (company_id,),
    )
    return render_template("company_detail.html", company=company, contracts=contracts, projects=projects, maturity=maturity, files=files, users=users, questionnaires=questionnaires, area_options=area_options, pending_changes=pending_changes)


@app.route("/company/<int:company_id>/project/new", methods=("GET", "POST"))
@login_required
@admin_required
def project_new(company_id):
    company = query_one("SELECT * FROM companies WHERE id = ?", (company_id,))
    if not company:
        abort(404)
    if request.method == "POST":
        cur = execute(
            """
            INSERT INTO projects (company_id, name, objective, phase, progress, start_date, end_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company_id,
                request.form.get("name"),
                request.form.get("objective"),
                request.form.get("phase") or "Onboarding",
                int(request.form.get("progress") or 0),
                request.form.get("start_date"),
                request.form.get("end_date"),
                request.form.get("status") or "Em andamento",
            ),
        )
        log_action("Projeto criado", "projects", cur.lastrowid)
        flash("Projeto criado com sucesso.", "success")
        return redirect(url_for("project_detail", project_id=cur.lastrowid))
    return render_template("project_form.html", company=company)


@app.route("/project/<int:project_id>", methods=("GET", "POST"))
@login_required
def project_detail(project_id):
    project = get_project_with_company(project_id)
    if request.method == "POST":
        if g.user["role"] not in ADMIN_ROLES:
            abort(403)
        execute(
            """
            UPDATE projects
            SET name = ?, objective = ?, phase = ?, progress = ?, start_date = ?, end_date = ?, status = ?
            WHERE id = ?
            """,
            (
                request.form.get("name"),
                request.form.get("objective"),
                request.form.get("phase"),
                int(request.form.get("progress") or 0),
                request.form.get("start_date"),
                request.form.get("end_date"),
                request.form.get("status"),
                project_id,
            ),
        )
        log_action("Projeto atualizado", "projects", project_id)
        flash("Projeto atualizado.", "success")
        return redirect(url_for("project_detail", project_id=project_id))
    tasks = query_all("SELECT * FROM tasks WHERE project_id = ? ORDER BY due_date ASC", (project_id,))
    notes = query_all(
        """
        SELECT n.*, u.name AS author_name
        FROM project_notes n
        LEFT JOIN users u ON u.id = n.author_id
        WHERE n.project_id = ? AND (n.visibility = 'Cliente' OR ? = 1)
        ORDER BY n.created_at DESC
        """,
        (project_id, 1 if g.user["role"] in ADMIN_ROLES else 0),
    )
    stages = get_project_stages(project_id, include_internal=(g.user["role"] in ADMIN_ROLES))
    return render_template("project_detail.html", project=project, tasks=tasks, notes=notes, stages=stages)


@app.route("/stage/<int:stage_id>")
@login_required
def stage_detail(stage_id):
    stage = query_one(
        """
        SELECT
            s.*,
            p.name AS project_name,
            p.company_id,
            p.objective AS project_objective,
            p.phase AS project_phase,
            p.status AS project_status,
            p.progress AS project_progress,
            c.name AS company_name
        FROM project_stages s
        JOIN projects p ON p.id = s.project_id
        JOIN companies c ON c.id = p.company_id
        WHERE s.id = ?
        """,
        (stage_id,),
    )
    if not stage:
        abort(404)
    require_company_access(stage["company_id"])
    if g.user["role"] not in ADMIN_ROLES and stage["visible_to_client"] != 1:
        abort(403)

    stages = get_project_stages(stage["project_id"], include_internal=(g.user["role"] in ADMIN_ROLES))
    tasks = query_all(
        """
        SELECT * FROM tasks
        WHERE project_id = ?
        ORDER BY CASE status WHEN 'Pendente' THEN 1 WHEN 'Em andamento' THEN 2 ELSE 3 END, due_date ASC
        """,
        (stage["project_id"],),
    )
    notes = query_all(
        """
        SELECT n.*, u.name AS author_name
        FROM project_notes n
        LEFT JOIN users u ON u.id = n.author_id
        WHERE n.project_id = ? AND (n.visibility = 'Cliente' OR ? = 1)
        ORDER BY n.created_at DESC
        """,
        (stage["project_id"], 1 if g.user["role"] in ADMIN_ROLES else 0),
    )
    return render_template("stage_detail.html", stage=stage, stages=stages, tasks=tasks, notes=notes)


@app.route("/project/<int:project_id>/task/new", methods=("POST",))
@login_required
def task_new(project_id):
    project = get_project_with_company(project_id)
    if g.user["role"] == "client_viewer":
        abort(403)
    status = request.form.get("status") or "Pendente"
    due_date = request.form.get("due_date")
    completed_at = request.form.get("completed_at") or (today_iso() if status == "Concluída" else None)
    cur = execute(
        """
        INSERT INTO tasks (project_id, title, description, owner, responsible_team, start_date, due_date, original_due_date, completed_at, extension_reason, status, priority, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            request.form.get("title"),
            request.form.get("description"),
            request.form.get("owner"),
            request.form.get("responsible_team") or "Atacarejo Insights",
            request.form.get("start_date"),
            due_date,
            due_date,
            completed_at,
            request.form.get("extension_reason"),
            status,
            request.form.get("priority") or "Média",
            now_iso(),
        ),
    )
    log_action("Tarefa criada", "tasks", cur.lastrowid)
    flash("Tarefa adicionada com responsável, datas e status gerencial.", "success")
    return redirect(url_for("project_detail", project_id=project_id))


@app.route("/task/<int:task_id>/status", methods=("POST",))
@login_required
def task_status(task_id):
    task = query_one(
        """
        SELECT t.*, p.company_id
        FROM tasks t
        JOIN projects p ON p.id = t.project_id
        WHERE t.id = ?
        """,
        (task_id,),
    )
    if not task:
        abort(404)
    require_company_access(task["company_id"])
    if g.user["role"] == "client_viewer":
        abort(403)
    new_status = request.form.get("status") or "Pendente"
    completed_at = task["completed_at"]
    if new_status == "Concluída" and not completed_at:
        completed_at = today_iso()
    if new_status != "Concluída":
        completed_at = request.form.get("completed_at") or None
    new_due_date = request.form.get("due_date") or task["due_date"]
    execute(
        """
        UPDATE tasks
        SET status = ?, completed_at = ?, due_date = ?, extension_reason = COALESCE(NULLIF(?, ''), extension_reason)
        WHERE id = ?
        """,
        (new_status, completed_at, new_due_date, request.form.get("extension_reason"), task_id),
    )
    log_action("Status de tarefa atualizado", "tasks", task_id)
    flash("Status atualizado. A classificação de prazo foi recalculada.", "success")
    return redirect(url_for("project_detail", project_id=task["project_id"]))


@app.route("/task/<int:task_id>/update", methods=("POST",))
@login_required
def task_update(task_id):
    task = query_one(
        """
        SELECT t.*, p.company_id
        FROM tasks t
        JOIN projects p ON p.id = t.project_id
        WHERE t.id = ?
        """,
        (task_id,),
    )
    if not task:
        abort(404)
    require_company_access(task["company_id"])
    if g.user["role"] not in ADMIN_ROLES:
        abort(403)
    status = request.form.get("status") or task["status"]
    completed_at = request.form.get("completed_at") or (today_iso() if status == "Concluída" else None)
    execute(
        """
        UPDATE tasks
        SET title = ?, description = ?, owner = ?, responsible_team = ?, start_date = ?, due_date = ?, completed_at = ?, extension_reason = ?, status = ?, priority = ?
        WHERE id = ?
        """,
        (
            request.form.get("title"),
            request.form.get("description"),
            request.form.get("owner"),
            request.form.get("responsible_team") or "Atacarejo Insights",
            request.form.get("start_date"),
            request.form.get("due_date"),
            completed_at,
            request.form.get("extension_reason"),
            status,
            request.form.get("priority") or "Média",
            task_id,
        ),
    )
    log_action("Tarefa atualizada", "tasks", task_id)
    flash("Tarefa atualizada.", "success")
    return redirect(url_for("project_detail", project_id=task["project_id"]))


@app.route("/project/<int:project_id>/note/new", methods=("POST",))
@login_required
def note_new(project_id):
    project = get_project_with_company(project_id)
    if g.user["role"] == "client_viewer":
        abort(403)
    visibility = request.form.get("visibility") or "Cliente"
    if g.user["role"] not in ADMIN_ROLES:
        visibility = "Cliente"
    execute(
        "INSERT INTO project_notes (project_id, author_id, note, visibility, created_at) VALUES (?, ?, ?, ?, ?)",
        (project_id, g.user["id"], request.form.get("note"), visibility, now_iso()),
    )
    log_action("Nota de projeto criada", "projects", project_id)
    flash("Comentário registrado.", "success")
    return redirect(url_for("project_detail", project_id=project_id))


@app.route("/company/<int:company_id>/diagnostic", methods=("GET", "POST"))
@login_required
def diagnostic(company_id):
    require_company_access(company_id)
    company = query_one("SELECT * FROM companies WHERE id = ?", (company_id,))
    if not company:
        abort(404)
    areas = query_all("SELECT * FROM diagnostic_areas ORDER BY id")
    if request.method == "POST":
        if g.user["role"] == "client_viewer":
            abort(403)
        for area in areas:
            score = int(request.form.get(f"score_{area['id']}") or 1)
            comment = request.form.get(f"comment_{area['id']}")
            score = max(1, min(5, score))
            execute(
                """
                INSERT INTO diagnostic_answers (company_id, area_id, score, comment, updated_by, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(company_id, area_id)
                DO UPDATE SET score = excluded.score, comment = excluded.comment, updated_by = excluded.updated_by, updated_at = excluded.updated_at
                """,
                (company_id, area["id"], score, comment, g.user["id"], now_iso()),
            )
        log_action("Diagnóstico atualizado", "companies", company_id)
        flash("Diagnóstico salvo com sucesso.", "success")
        return redirect(url_for("diagnostic", company_id=company_id))
    answers = {r["area_id"]: r for r in query_all("SELECT * FROM diagnostic_answers WHERE company_id = ?", (company_id,))}
    return render_template("diagnostic.html", company=company, areas=areas, answers=answers)


@app.route("/admin/areas/new", methods=("POST",))
@login_required
@admin_required
def area_new():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    company_id = request.form.get("company_id")
    if not name:
        flash("Informe o nome da área.", "error")
    else:
        area_id = ensure_area_exists(name, description)
        flash("Área incluída no mapeamento de diagnóstico e imersões.", "success")
    if company_id:
        return redirect(url_for("company_detail", company_id=int(company_id)))
    return redirect(url_for("clients"))


@app.route("/company/<int:company_id>/questionnaire/new", methods=("POST",))
@login_required
@admin_required
def questionnaire_new(company_id):
    company = query_one("SELECT * FROM companies WHERE id = ?", (company_id,))
    if not company:
        abort(404)
    title = request.form.get("title")
    if not title:
        flash("Informe o título do questionário.", "error")
        return redirect(url_for("company_detail", company_id=company_id))

    custom_area = request.form.get("custom_area", "").strip()
    selected_area = request.form.get("context_area", "").strip()
    context_area = custom_area or selected_area
    if context_area:
        ensure_area_exists(context_area)

    qcur = execute(
        """
        INSERT INTO diagnostic_questionnaires (company_id, title, context_area, target_role, description, status, visible_to_client, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            company_id,
            title,
            context_area,
            request.form.get("target_role"),
            request.form.get("description"),
            request.form.get("status") or "Aberto",
            1 if request.form.get("visible_to_client", "1") == "1" else 0,
            g.user["id"],
            now_iso(),
        ),
    )
    qid = qcur.lastrowid
    raw_questions = request.form.get("questions") or ""
    questions = [q.strip() for q in raw_questions.splitlines() if q.strip()]
    if not questions and context_area in AREA_QUESTION_TEMPLATES:
        questions = AREA_QUESTION_TEMPLATES[context_area]
    if not questions:
        questions = [
            "Descreva o panorama atual da área.",
            "Quais são os principais gargalos percebidos?",
            "Quais indicadores são acompanhados e com qual frequência?",
            "Quais informações faltam para melhorar a tomada de decisão?",
            "Quais oportunidades deveriam ser priorizadas nos próximos 90 dias?",
        ]
    for idx, question in enumerate(questions, start=1):
        execute(
            "INSERT INTO diagnostic_questions (questionnaire_id, question_text, question_type, sort_order) VALUES (?, ?, 'textarea', ?)",
            (qid, question, idx),
        )
    log_action("Questionário criado", "diagnostic_questionnaires", qid)
    flash("Questionário de imersão criado com sucesso.", "success")
    return redirect(url_for("questionnaire_detail", questionnaire_id=qid))


@app.route("/questionnaire/<int:questionnaire_id>", methods=("GET", "POST"))
@login_required
def questionnaire_detail(questionnaire_id):
    questionnaire = query_one(
        """
        SELECT q.*, c.name AS company_name, c.id AS company_id
        FROM diagnostic_questionnaires q
        JOIN companies c ON c.id = q.company_id
        WHERE q.id = ?
        """,
        (questionnaire_id,),
    )
    if not questionnaire:
        abort(404)
    require_company_access(questionnaire["company_id"])
    if g.user["role"] not in ADMIN_ROLES and questionnaire["visible_to_client"] != 1:
        abort(403)

    questions = query_all("SELECT * FROM diagnostic_questions WHERE questionnaire_id = ? ORDER BY sort_order, id", (questionnaire_id,))
    if request.method == "POST":
        if g.user["role"] == "client_viewer":
            abort(403)
        created_direct = 0
        pending_review = 0
        for question in questions:
            answer = request.form.get(f"answer_{question['id']}") or ""
            existing = query_one(
                "SELECT * FROM diagnostic_questionnaire_answers WHERE questionnaire_id = ? AND question_id = ? AND user_id = ?",
                (questionnaire_id, question["id"], g.user["id"]),
            )
            if g.user["role"] in ADMIN_ROLES:
                execute(
                    """
                    INSERT INTO diagnostic_questionnaire_answers (questionnaire_id, question_id, user_id, answer_text, answered_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(questionnaire_id, question_id, user_id)
                    DO UPDATE SET answer_text = excluded.answer_text, answered_at = excluded.answered_at
                    """,
                    (questionnaire_id, question["id"], g.user["id"], answer, now_iso()),
                )
                created_direct += 1
            elif existing:
                if create_change_request(questionnaire["company_id"], "questionnaire_answer", existing["id"], f"Resposta: {question['question_text'][:90]}", existing["answer_text"], answer):
                    pending_review += 1
            else:
                execute(
                    """
                    INSERT INTO diagnostic_questionnaire_answers (questionnaire_id, question_id, user_id, answer_text, answered_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (questionnaire_id, question["id"], g.user["id"], answer, now_iso()),
                )
                created_direct += 1
        if questionnaire["status"] == "Aberto":
            execute("UPDATE diagnostic_questionnaires SET status = 'Em coleta' WHERE id = ?", (questionnaire_id,))
        log_action("Questionário respondido/alterado", "diagnostic_questionnaires", questionnaire_id)
        if pending_review:
            flash(f"Respostas novas foram registradas. {pending_review} alteração(ões) foram enviadas para aprovação do administrador.", "success")
        else:
            flash("Respostas registradas com sucesso.", "success")
        return redirect(url_for("questionnaire_detail", questionnaire_id=questionnaire_id))

    answers = query_all(
        """
        SELECT a.*, u.name AS user_name, u.email AS user_email, u.role AS user_role, dq.question_text, dq.sort_order
        FROM diagnostic_questionnaire_answers a
        JOIN users u ON u.id = a.user_id
        JOIN diagnostic_questions dq ON dq.id = a.question_id
        WHERE a.questionnaire_id = ?
        ORDER BY u.name, dq.sort_order, dq.id
        """,
        (questionnaire_id,),
    )
    respondents = query_all(
        """
        SELECT u.id, u.name, u.email, u.role, MAX(a.answered_at) AS last_answer, COUNT(a.id) AS answers_count
        FROM diagnostic_questionnaire_answers a
        JOIN users u ON u.id = a.user_id
        WHERE a.questionnaire_id = ?
        GROUP BY u.id
        ORDER BY last_answer DESC
        """,
        (questionnaire_id,),
    )
    my_answers = {r["question_id"]: r for r in query_all("SELECT * FROM diagnostic_questionnaire_answers WHERE questionnaire_id = ? AND user_id = ?", (questionnaire_id, g.user["id"]))}
    pending_changes = query_all(
        """
        SELECT cr.*, u.name AS user_name
        FROM change_requests cr
        LEFT JOIN users u ON u.id = cr.user_id
        WHERE cr.company_id = ? AND cr.entity_type = 'questionnaire_answer' AND cr.status = 'Pendente'
        ORDER BY cr.created_at DESC
        """,
        (questionnaire["company_id"],),
    )
    return render_template("questionnaire_detail.html", questionnaire=questionnaire, questions=questions, answers=answers, respondents=respondents, my_answers=my_answers, pending_changes=pending_changes)


@app.route("/questionnaire/<int:questionnaire_id>/status", methods=("POST",))
@login_required
@admin_required
def questionnaire_status(questionnaire_id):
    questionnaire = query_one("SELECT * FROM diagnostic_questionnaires WHERE id = ?", (questionnaire_id,))
    if not questionnaire:
        abort(404)
    execute(
        "UPDATE diagnostic_questionnaires SET status = ?, visible_to_client = ? WHERE id = ?",
        (
            request.form.get("status") or questionnaire["status"],
            1 if request.form.get("visible_to_client", "1") == "1" else 0,
            questionnaire_id,
        ),
    )
    flash("Status do questionário atualizado.", "success")
    return redirect(url_for("questionnaire_detail", questionnaire_id=questionnaire_id))


@app.route("/project/<int:project_id>/stage/new", methods=("POST",))
@login_required
@admin_required
def stage_new(project_id):
    project = get_project_with_company(project_id)
    execute(
        """
        INSERT INTO project_stages (project_id, title, description, sort_order, status, start_date, end_date, visible_to_client, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            request.form.get("title"),
            request.form.get("description"),
            int(request.form.get("sort_order") or 0),
            request.form.get("status") or "Pendente",
            request.form.get("start_date"),
            request.form.get("end_date"),
            1 if request.form.get("visible_to_client", "1") == "1" else 0,
            now_iso(),
        ),
    )
    flash("Etapa adicionada à jornada do projeto.", "success")
    return redirect(url_for("project_detail", project_id=project["id"]))


@app.route("/stage/<int:stage_id>/update", methods=("POST",))
@login_required
@admin_required
def stage_update(stage_id):
    stage = query_one(
        """
        SELECT s.*, p.company_id
        FROM project_stages s
        JOIN projects p ON p.id = s.project_id
        WHERE s.id = ?
        """,
        (stage_id,),
    )
    if not stage:
        abort(404)
    require_company_access(stage["company_id"])
    execute(
        """
        UPDATE project_stages
        SET title = ?, description = ?, sort_order = ?, status = ?, start_date = ?, end_date = ?, visible_to_client = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            request.form.get("title"),
            request.form.get("description"),
            int(request.form.get("sort_order") or 0),
            request.form.get("status") or "Pendente",
            request.form.get("start_date"),
            request.form.get("end_date"),
            1 if request.form.get("visible_to_client", "1") == "1" else 0,
            now_iso(),
            stage_id,
        ),
    )
    # Sincroniza a fase textual do projeto com a etapa em andamento mais recente.
    current = query_one("SELECT title FROM project_stages WHERE project_id = ? AND status = 'Em andamento' ORDER BY sort_order LIMIT 1", (stage["project_id"],))
    if current:
        execute("UPDATE projects SET phase = ? WHERE id = ?", (current["title"], stage["project_id"]))
    flash("Etapa atualizada e visibilidade do cliente revisada.", "success")
    return redirect(url_for("project_detail", project_id=stage["project_id"]))


@app.route("/admin/users", methods=("GET", "POST"))
@login_required
@admin_required
def users():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        company_id = request.form.get("company_id") or None
        profile_model = request.form.get("profile_model") or None
        role = profile_to_role(profile_model, request.form.get("role"))
        if role in CLIENT_ROLES and not company_id:
            flash("Usuários de cliente precisam estar vinculados a uma empresa.", "error")
        else:
            try:
                cur = execute(
                    """
                    INSERT INTO users (name, email, password_hash, role, profile_model, department_area, access_scope, permission_notes, company_id, active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                    """,
                    (
                        request.form.get("name"),
                        email,
                        generate_password_hash(request.form.get("password") or "123456"),
                        role,
                        profile_model,
                        request.form.get("department_area"),
                        request.form.get("access_scope") or ("company_only" if role in CLIENT_ROLES else "assigned_projects"),
                        request.form.get("permission_notes"),
                        company_id,
                        now_iso(),
                    ),
                )
                user_id = cur.lastrowid
                for project_id in request.form.getlist("project_ids"):
                    if project_id:
                        execute(
                            "INSERT OR IGNORE INTO user_project_assignments (user_id, project_id, assigned_at) VALUES (?, ?, ?)",
                            (user_id, int(project_id), now_iso()),
                        )
                flash("Usuário criado com perfil modelo, escopo de acesso e vínculos de projeto.", "success")
                log_action("Usuário criado", "users", user_id)
            except sqlite3.IntegrityError:
                flash("Já existe um usuário com esse e-mail.", "error")
    users_rows = query_all(
        """
        SELECT u.*, c.name AS company_name,
               GROUP_CONCAT(p.name, ' | ') AS assigned_projects
        FROM users u
        LEFT JOIN companies c ON c.id = u.company_id
        LEFT JOIN user_project_assignments upa ON upa.user_id = u.id
        LEFT JOIN projects p ON p.id = upa.project_id
        GROUP BY u.id
        ORDER BY u.created_at DESC
        """
    )
    companies = query_all("SELECT id, name FROM companies ORDER BY name")
    projects = query_all("SELECT p.id, p.name, c.name AS company_name FROM projects p JOIN companies c ON c.id = p.company_id ORDER BY c.name, p.name")
    return render_template("users.html", users=users_rows, companies=companies, projects=projects)


@app.route("/admin/users/<int:user_id>/update", methods=("POST",))
@login_required
@admin_required
def user_update(user_id):
    user = query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    if not user:
        abort(404)
    profile_model = request.form.get("profile_model") or None
    role = profile_to_role(profile_model, request.form.get("role") or user["role"])
    company_id = request.form.get("company_id") or None
    active = 1 if request.form.get("active") == "1" else 0
    if role in CLIENT_ROLES and not company_id:
        flash("Usuários de cliente precisam estar vinculados a uma empresa.", "error")
        return redirect(url_for("users"))
    execute(
        """
        UPDATE users
        SET name = ?, role = ?, profile_model = ?, department_area = ?, access_scope = ?, permission_notes = ?, company_id = ?, active = ?
        WHERE id = ?
        """,
        (
            request.form.get("name"),
            role,
            profile_model,
            request.form.get("department_area"),
            request.form.get("access_scope"),
            request.form.get("permission_notes"),
            company_id,
            active,
            user_id,
        ),
    )
    execute("DELETE FROM user_project_assignments WHERE user_id = ?", (user_id,))
    for project_id in request.form.getlist("project_ids"):
        if project_id:
            execute(
                "INSERT OR IGNORE INTO user_project_assignments (user_id, project_id, assigned_at) VALUES (?, ?, ?)",
                (user_id, int(project_id), now_iso()),
            )
    log_action("Perfil de usuário atualizado", "users", user_id)
    flash("Perfil, escopo e vínculos de acesso atualizados.", "success")
    return redirect(url_for("users"))


@app.route("/client/usuarios", methods=("GET", "POST"))
@login_required
def client_users():
    if g.user["role"] in ADMIN_ROLES:
        return redirect(url_for("users"))
    if g.user["role"] != "client_admin":
        abort(403)
    company_id = g.user["company_id"]
    company = query_one("SELECT * FROM companies WHERE id = ?", (company_id,))
    if not company:
        abort(404)
    if request.method == "POST":
        payload = {
            "name": request.form.get("name"),
            "email": (request.form.get("email") or "").strip().lower(),
            "password": request.form.get("password") or "cliente123",
            "profile_model": request.form.get("profile_model") or "colaborador_respondente",
            "department_area": request.form.get("department_area"),
            "access_scope": request.form.get("access_scope") or "company_only",
            "permission_notes": request.form.get("permission_notes"),
        }
        if not payload["name"] or not payload["email"]:
            flash("Informe nome e e-mail do usuário solicitado.", "error")
        else:
            create_change_request(company_id, "user_create", None, "Novo usuário do cliente", "", json.dumps(payload, ensure_ascii=False))
            flash("Solicitação de usuário enviada para aprovação da Atacarejo Insights.", "success")
        return redirect(url_for("client_users"))
    company_users = query_all("SELECT * FROM users WHERE company_id = ? ORDER BY active DESC, name", (company_id,))
    pending = query_all(
        """
        SELECT cr.*, u.name AS user_name
        FROM change_requests cr
        LEFT JOIN users u ON u.id = cr.user_id
        WHERE cr.company_id = ? AND cr.entity_type = 'user_create'
        ORDER BY cr.created_at DESC
        """,
        (company_id,),
    )
    return render_template("client_users.html", company=company, company_users=company_users, pending=pending)


@app.route("/company/<int:company_id>/file/new", methods=("POST",))
@login_required
def file_new(company_id):
    require_company_access(company_id)
    if g.user["role"] == "client_viewer":
        abort(403)
    payload = {
        "title": request.form.get("title"),
        "file_type": request.form.get("file_type"),
        "status": request.form.get("status") or "Enviado pelo cliente",
        "notes": request.form.get("notes"),
        "due_date": request.form.get("due_date"),
    }
    if g.user["role"] in ADMIN_ROLES:
        execute(
            """
            INSERT INTO files_registry (company_id, title, file_type, status, notes, due_date, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (company_id, payload["title"], payload["file_type"], payload["status"], payload["notes"], payload["due_date"], now_iso()),
        )
        flash("Item de documento/dado registrado.", "success")
    else:
        create_change_request(company_id, "file_registry_new", None, "Novo dado/documento", "", json.dumps(payload, ensure_ascii=False))
        flash("Informação enviada para aprovação da Atacarejo Insights antes de entrar oficialmente no ambiente do projeto.", "success")
    return redirect(url_for("company_detail", company_id=company_id))


@app.route("/report/company/<int:company_id>")
@login_required
def company_report(company_id):
    require_company_access(company_id)
    company = query_one("SELECT * FROM companies WHERE id = ?", (company_id,))
    if not company:
        abort(404)
    projects = query_all("SELECT * FROM projects WHERE company_id = ? ORDER BY id DESC", (company_id,))
    maturity = query_all(
        """
        SELECT a.name, a.description, COALESCE(d.score, 0) AS score, d.comment
        FROM diagnostic_areas a
        LEFT JOIN diagnostic_answers d ON d.area_id = a.id AND d.company_id = ?
        ORDER BY a.id
        """,
        (company_id,),
    )
    tasks = query_all(
        """
        SELECT t.*, p.name AS project_name
        FROM tasks t
        JOIN projects p ON p.id = t.project_id
        WHERE p.company_id = ?
        ORDER BY t.due_date ASC
        """,
        (company_id,),
    )
    return render_template("company_report.html", company=company, projects=projects, maturity=maturity, tasks=tasks)


# Service worker desativado nesta versão local para evitar cache antigo do Chrome.

# Inicializa o banco também quando o app é importado pelo Gunicorn/Render.
# No ambiente local, esta chamada é idempotente porque o schema usa CREATE TABLE IF NOT EXISTS.
try:
    print("[Atacarejo Insights] Importando app Flask...", file=sys.stderr, flush=True)
    init_db()
    print("[Atacarejo Insights] App inicializado com sucesso.", file=sys.stderr, flush=True)
except Exception:
    print("[Atacarejo Insights] FALHA AO INICIALIZAR O APP.", file=sys.stderr, flush=True)
    traceback.print_exc(file=sys.stderr)
    raise


@app.route("/reset-demo-db")
def reset_demo_db():
    # Rota técnica temporária para limpar banco SQLite de demonstração no Render quando versões antigas
    # deixarem schema incompatível em /tmp. Use somente durante testes.
    if request.args.get("confirmar") != "SIM":
        return "Para recriar o banco de demonstração, acesse /reset-demo-db?confirmar=SIM", 400
    try:
        db_path = app.config["DATABASE"]
        try:
            if hasattr(g, "db") and g.db is not None:
                g.db.close()
                g.pop("db", None)
        except Exception:
            pass
        if os.path.exists(db_path):
            os.remove(db_path)
        init_db()
        session.clear()
        return f"OK - banco recriado em {db_path}. Volte para /", 200
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        return f"ERRO ao recriar banco: {type(exc).__name__}: {exc}", 500


@app.route("/health")
def health():
    return f"OK - Atacarejo Insights Portal ativo. Banco: {app.config['DATABASE']}", 200


@app.route("/health-db")
def health_db():
    try:
        users = query_one("SELECT COUNT(*) AS c FROM users")["c"]
        companies = query_one("SELECT COUNT(*) AS c FROM companies")["c"]
        return f"OK DB - usuarios={users}; empresas={companies}; database={app.config['DATABASE']}", 200
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        return f"ERRO DB - {type(exc).__name__}: {exc}", 500


def safe_error_response(code, title, message):
    """Resposta de erro independente de template.

    Importante para o Render: se a causa do erro for justamente carregamento de
    templates, o handler de erro não pode chamar render_template(), pois isso
    cria erro em cascata e mascara a causa principal.
    """
    import html as _html
    title_safe = _html.escape(str(title))
    message_safe = _html.escape(str(message))
    code_safe = _html.escape(str(code))
    html = f"""
    <!doctype html>
    <html lang="pt-BR">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{code_safe} - Atacarejo Insights Portal</title>
        <style>
            :root {{ --roxo:#6610f2; --laranja:#ff9f1a; --bg:#06020b; --card:#151020; }}
            * {{ box-sizing:border-box; }}
            body {{ margin:0; min-height:100vh; display:grid; place-items:center;
                background:radial-gradient(circle at 80% 20%, rgba(102,16,242,.25), transparent 28%), var(--bg);
                color:#f8f7ff; font-family:Arial, Helvetica, sans-serif; padding:24px; }}
            .card {{ width:min(860px, 100%); padding:36px; border-radius:24px;
                background:rgba(21,16,32,.94); border:1px solid rgba(255,255,255,.12);
                box-shadow:0 24px 80px rgba(0,0,0,.35); }}
            .badge {{ display:inline-block; padding:8px 14px; border-radius:999px;
                background:linear-gradient(90deg,var(--roxo),var(--laranja)); font-weight:700; margin-bottom:18px; }}
            h1 {{ margin:0 0 14px; font-size:clamp(26px,4vw,38px); }}
            p {{ color:#ddd6f3; line-height:1.6; font-size:16px; }}
            a {{ color:var(--laranja); font-weight:700; text-decoration:none; }}
            .actions {{ display:flex; gap:12px; flex-wrap:wrap; margin-top:22px; }}
            .btn {{ display:inline-block; padding:12px 16px; border-radius:12px; background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.14); }}
            code {{ color:#ffcf7a; background:rgba(255,255,255,.06); padding:2px 6px; border-radius:6px; }}
            .small {{ color:#aaa; font-size:13px; margin-top:22px; }}
        </style>
    </head>
    <body>
        <main class="card">
            <div class="badge">Atacarejo Insights Portal</div>
            <h1>{title_safe}</h1>
            <p>{message_safe}</p>
            <div class="actions">
                <a class="btn" href="/">Página inicial</a>
                <a class="btn" href="/login">Login</a>
                <a class="btn" href="/health">Teste /health</a>
                <a class="btn" href="/health-db">Teste /health-db</a>
                <a class="btn" href="/limpar-sessao">Limpar sessão</a>
            </div>
            <p class="small">Esta resposta não depende de <code>templates/error.html</code>. Se ela aparecer, consulte os Logs do Render para o traceback original acima desta mensagem.</p>
        </main>
    </body>
    </html>
    """
    return html, int(code)


@app.errorhandler(500)
def internal_error(e):
    traceback.print_exc(file=sys.stderr)
    original = getattr(e, "original_exception", None) or e
    detail = f"Detalhe técnico: {type(original).__name__}: {original}"
    return safe_error_response(500, "Erro interno no servidor", "O servidor encontrou uma falha ao processar a solicitação. " + detail + " | Acesse /health-db para validar o banco e veja os Logs do Render para o traceback completo.")


@app.errorhandler(403)
def forbidden(e):
    return safe_error_response(403, "Acesso negado", "Este ambiente respeita isolamento por cliente e perfil de usuário.")


@app.errorhandler(404)
def not_found(e):
    return safe_error_response(404, "Página não encontrada", "Página ou registro não encontrado.")


def log_template_diagnostics():
    templates_dir = os.path.join(BASE_DIR, "templates")
    required = ["public_home.html", "login.html", "lead_register.html", "admin_dashboard.html", "client_dashboard.html"]
    print(f"[Atacarejo Insights] BASE_DIR={BASE_DIR}", file=sys.stderr)
    print(f"[Atacarejo Insights] templates_dir={templates_dir} exists={os.path.isdir(templates_dir)}", file=sys.stderr)
    if os.path.isdir(templates_dir):
        existing = sorted(os.listdir(templates_dir))
        print(f"[Atacarejo Insights] templates encontrados={existing[:40]}", file=sys.stderr)
    missing = [t for t in required if not os.path.exists(os.path.join(templates_dir, t))]
    if missing:
        print(f"[Atacarejo Insights] ATENCAO templates ausentes={missing}", file=sys.stderr)


log_template_diagnostics()

if __name__ == "__main__":
    host = os.environ.get("APP_HOST", "0.0.0.0" if IS_RENDER else "127.0.0.1")
    port = int(os.environ.get("PORT") or os.environ.get("APP_PORT", "5070"))
    print(f"[Atacarejo Insights] Servidor iniciando em {host}:{port}", file=sys.stderr, flush=True)
    app.run(debug=False, use_reloader=False, host=host, port=port)
