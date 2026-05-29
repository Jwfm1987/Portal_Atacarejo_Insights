# Atacarejo Insights — v14 Site Público + Portal do Cliente

Esta versão transforma a tela institucional em uma página pública inicial para uso no domínio `atacarejoinsights.com.br`, mantendo o portal restrito para clientes contratados.

## Principais novidades

- Página pública inicial com conteúdo institucional, mercado, metodologia, cases e CTA de cadastro.
- Cadastro de interesse para novos leads vindos do site, redes sociais ou flyers.
- Login separado para clientes já contratados.
- Administração de leads no painel do administrador.
- Conversão de lead em cliente, com criação de empresa, projeto inicial, jornada e usuário de acesso definitivo.
- Aprovação administrativa para alterações feitas por usuários do cliente.
- Alterações cadastrais entram em fila de aprovação.
- Edições de respostas de questionários entram em fila de aprovação.
- Informações/dados enviados pelo cliente entram em aprovação antes de aparecerem oficialmente.
- Tarefas com responsável, equipe responsável, início, prazo, prazo original, conclusão, prorrogação, cancelamento e classificação automática.

## Como executar no Windows

1. Extraia o ZIP.
2. Abra a pasta extraída.
3. Execute `INICIAR_APLICATIVO_WINDOWS.bat`.
4. Acesse `http://localhost:5070`.

## Acessos de demonstração

Administrador:
- E-mail: `admin@atacarejoinsights.com`
- Senha: `admin123`

Cliente:
- E-mail: `cliente@demo.com`
- Senha: `cliente123`

Usuários simulados de áreas:
- `operacoes@demo.com` / `cliente123`
- `compras@demo.com` / `cliente123`
- `vendas@demo.com` / `cliente123`
- `diretoria@demo.com` / `cliente123`

## Observação

Esta versão continua sendo um MVP local em Flask/SQLite. Para publicar em produção no domínio comprado, o ideal é migrar para ambiente com HTTPS, banco PostgreSQL, autenticação profissional, backup automático, política LGPD, servidor seguro e rotina de deploy.


## Versão 15 — Cadastro simplificado e gestão de usuários

- Landing page mantém o cadastro inicial enxuto: nome do solicitante, empresa, UF da matriz, telefone e e-mail.
- Dados completos entram depois, no ambiente do cliente, após reunião, apresentação do projeto e formalização do contrato.
- Solicitações de alteração feitas pelo cliente continuam sujeitas à análise da Atacarejo Insights.
- A área de usuários agora possui perfis modelo internos e de cliente, escopo de acesso, área/função e vínculos com projetos.
- Clientes administradores podem solicitar novos usuários, com aprovação obrigatória do administrador.


## Versão 16 — Landing page pública e login por permissão

- A página inicial pública passa a ser o primeiro contato com clientes e leads.
- A área institucional sobre a Atacarejo Insights e o mercado fica antes do login.
- O ambiente do cliente fica focado apenas em projeto, diagnóstico, imersões, dados, usuários e acompanhamento.
- O login direciona automaticamente o usuário para o painel conforme perfil/permissão.
