import os
import json
import sqlite3
from datetime import datetime, date
from functools import wraps

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "instance", "atacarejo_insights.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-atacarejo-insights-change-me")
app.config["DATABASE"] = DATABASE

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
    os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)
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
    user_id = session.get("user_id")
    g.user = None
    if user_id is not None:
        g.user = query_one("SELECT * FROM users WHERE id = ? AND active = 1", (user_id,))




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


@app.route("/")
def index():
    if g.user:
        return redirect_for_user(g.user)
    return render_template("public_home.html", content=get_client_about_content())


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
    return render_template("lead_register.html")


@app.route("/cadastro/recebido")
def public_register_success():
    return render_template("lead_register.html", success=True)


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
    return render_template("login.html")


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
init_db()


@app.route("/health")
def health():
    return f"OK - Atacarejo Insights Portal ativo na porta {os.environ.get('APP_PORT', '5070')}", 200


@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="Acesso negado. Este ambiente respeita isolamento por cliente e perfil de usuário."), 403


@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Página ou registro não encontrado."), 404


if __name__ == "__main__":
    app.run(debug=False, use_reloader=False, host=os.environ.get("APP_HOST", "127.0.0.1"), port=int(os.environ.get("APP_PORT", "5070")))
