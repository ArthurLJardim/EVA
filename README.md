# EVA - Bot SIGAA + e-mail academico + agenda

**EVA** e um assistente pessoal, local, para automatizar a vida academica. Ele roda no seu computador e centraliza tudo que costuma ficar espalhado entre o SIGAA, o e-mail e o Google Classroom, entregando prazos e avisos direto na sua agenda e na sua caixa de entrada.

Este projeto cria um bot local para:

- ler atualizacoes recebidas no e-mail academico;
- acessar o SIGAA e coletar atividades/provas;
- ler atividades, provas e avisos do Google Classroom;
- atualizar uma agenda sincronizada no PC e no iPhone;
- enviar aviso por e-mail quando faltar `3 dias` para o fim da atividade/prova;
- avisar por e-mail quando aparecer noticia pertinente sobre o curso ou area;
- classificar itens por prioridade;
- avisar em varios prazos antes do vencimento;
- detectar mudancas em atividades/provas ja conhecidas;
- enviar resumo diario;
- gerar dashboard local;
- enviar Telegram opcionalmente;
- fazer backup automatico do `.ics`;
- arquivar anexos de e-mail pertinentes para estudo de prova;
- gerar um arquivo `.ics` local como copia da agenda.

## Como a sincronizacao funciona

A forma mais estavel de aparecer no Windows e no iPhone e usar um calendario em nuvem, como Outlook ou Google Calendar. Este bot ja vem preparado para Outlook e Google Calendar:

- No PC: adicione a mesma conta Outlook no app Calendario/Outlook do Windows.
- No iPhone 16e: Ajustes > Apps > Calendario > Contas > Adicionar Conta > Outlook.com ou Microsoft Exchange > ative Calendarios.

Se sua faculdade usa Microsoft/Outlook, ainda da para adaptar para Microsoft Graph depois.

## Instalacao

No PowerShell, dentro desta pasta:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
Copy-Item .env.example .env
```

Edite o arquivo `.env` com seus dados.

## Outlook Calendar

Para usar Outlook, deixe no `.env`:

```text
CALENDAR_PROVIDER=outlook
```

Voce precisa criar um app no Microsoft Entra admin center:

1. Entre em App registrations.
2. Crie um app do tipo conta pessoal/organizacional conforme sua conta.
3. Copie o Application client ID para `OUTLOOK_CLIENT_ID`.
4. Em Authentication, habilite fluxo de cliente publico/mobile/desktop se necessario.
5. Em API permissions, adicione permissao delegada `Calendars.ReadWrite`.

Na primeira execucao, o bot mostra um codigo de login no terminal. Entre no endereco indicado, autorize sua conta Outlook e o token ficara salvo em:

```text
credentials/outlook_token_cache.bin
```

Se quiser usar um calendario especifico, preencha `OUTLOOK_CALENDAR_ID`; caso contrario use `primary`.

## Google Calendar

1. Acesse o Google Cloud Console.
2. Crie um projeto.
3. Ative a Google Calendar API.
4. Crie credenciais OAuth do tipo "Desktop app".
5. Baixe o JSON para `credentials/google_client_secret.json`.
6. Antes de agendar o sync automatico, autorize uma vez manualmente:

```powershell
python -m bot_faculdade calendar-auth
```

Isso abre o navegador para o login e salva o token em `credentials/google_token.json`. O `sync` automatico (agendado) nao abre navegador: se o token nao existir ou nao puder ser renovado sozinho, ele apenas avisa no log e pula o Google Calendar naquela execucao, sem travar o restante do sync. Rode `calendar-auth` novamente se isso acontecer.

Para usar Google Calendar em vez de Outlook, mude:

```text
CALENDAR_PROVIDER=google
```

Para enviar para os dois:

```text
CALENDAR_PROVIDER=both
```

## Google Classroom

No mesmo projeto do Google Cloud, ative tambem a Google Classroom API.

O bot usa acesso somente leitura para ver seus cursos, atividades/provas postadas, avisos/comunicados e materiais de aula.

Antes de agendar o sync automatico, autorize o Classroom uma vez manualmente:

```powershell
python -m bot_faculdade classroom-auth
```

Isso abre o navegador para o login e salva um token separado em:

```text
credentials/google_classroom_token.json
```

O `sync` automatico (agendado) nao abre navegador: se o token nao existir ou expirar sem possibilidade de renovacao automatica, ele apenas avisa no log e pula o Classroom naquela execucao, sem travar o restante do sync. Rode `classroom-auth` novamente se isso acontecer.

Para monitorar apenas cursos especificos, preencha no `.env`:

```text
CLASSROOM_COURSE_IDS=id_do_curso_1,id_do_curso_2
```

Se deixar vazio, ele tenta ler todos os cursos ativos permitidos pela sua conta.

## Uso

Rodar uma sincronizacao:

```powershell
.\.venv\Scripts\Activate.ps1
python -m bot_faculdade sync
```

Rodar sem acessar o SIGAA, usando apenas e-mail:

```powershell
python -m bot_faculdade sync --skip-sigaa
```

Rodar apenas Google Classroom:

```powershell
python -m bot_faculdade sync --only-classroom --notify
```

Ver itens encontrados:

```powershell
python -m bot_faculdade list
```

Enviar avisos pendentes:

```powershell
python -m bot_faculdade notify
```

Enviar resumo diario:

```powershell
python -m bot_faculdade summary
```

Gerar dashboard local:

```powershell
python -m bot_faculdade dashboard
```

Servir dashboard no navegador:

```powershell
python -m bot_faculdade serve-dashboard
```

Arquivar materiais de estudo relacionados a provas:

```powershell
python -m bot_faculdade archive-materials --notify
```

Listar materiais arquivados:

```powershell
python -m bot_faculdade list-materials
```

Listar noticias pertinentes encontradas:

```powershell
python -m bot_faculdade list-news
```

Enviar apenas avisos de noticias pendentes:

```powershell
python -m bot_faculdade notify-news
```

## Noticias pertinentes

O bot procura noticias, comunicados, avisos e informativos vindos do SIGAA/e-mail e so envia se encontrar tambem uma palavra importante configurada em `NEWS_KEYWORDS` no `.env`.

Exemplo:

```text
NEWS_KEYWORDS=curso,coordenacao,matricula,estagio,edital,bolsa,evento,palestra,monitoria,oportunidade
```

Assim ele evita avisar qualquer texto generico e foca em coisas que parecem relevantes para o curso ou para oportunidades na area.

## Lembretes multiplos

Configure os prazos em `REMINDER_DAYS`:

```text
REMINDER_DAYS=7,3,1,0
```

Com isso, o bot tenta avisar 7 dias antes, 3 dias antes, 1 dia antes e no dia. Ele registra cada aviso no banco para nao repetir o mesmo lembrete.

## Prioridade e urgencia

O bot classifica automaticamente como `alta`, `media` ou `baixa`.

Palavras como `prova`, `edital`, `matricula`, `prazo final`, `cancelado` e `adiado` entram como alta prioridade. O modo urgente usa `URGENT_KEYWORDS`; quando uma novidade recem-encontrada bate nesses termos, o bot manda aviso imediato no `sync --notify`.

## Mudancas detectadas

Quando um item ja conhecido muda de prazo, titulo, tipo, disciplina ou descricao, o bot grava no historico e envia um aviso de alteracao no `sync --notify`.

## Telegram opcional

Para receber tambem pelo Telegram, crie um bot com o BotFather e preencha:

```text
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Se esses campos ficarem vazios, o Telegram fica desativado e o e-mail continua funcionando normalmente.

## Dashboard

O dashboard fica em:

```text
exports/dashboard.html
```

Ele mostra proximos prazos, noticias recentes e mudancas detectadas. Para abrir por servidor local:
Ele tambem mostra os materiais de estudo arquivados para provas.

```powershell
python -m bot_faculdade serve-dashboard --port 8765
```

Depois acesse:

```text
http://127.0.0.1:8765/dashboard.html
```

## Backup da agenda

Sempre que o bot exporta `agenda_faculdade.ics`, ele tambem salva uma copia em:

```text
exports/backups
```

Para desativar:

```text
ICS_BACKUP_ENABLED=false
```

## Materiais de estudo para provas

Quando houver provas cadastradas, o bot procura no e-mail academico mensagens relacionadas ao titulo da prova ou disciplina, desde que parecam conter material de estudo, como `slides`, `apostila`, `lista`, `revisao`, `conteudo` ou `aula`.

Os anexos sao salvos em:

```text
materials/provas
```

Extensoes aceitas:

```text
STUDY_MATERIAL_EXTENSIONS=.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.zip,.rar,.txt,.png,.jpg,.jpeg
```

O bot registra cada arquivo no banco para nao baixar o mesmo anexo repetidas vezes. Ele nao apaga nem move mensagens do e-mail.

## Faltas e media por materia

A cada `sync`, o bot acessa o boletim de cada materia no SIGAA ("Ver Notas" dentro da Turma Virtual) e registra:

- o total de **faltas** da materia;
- as notas das unidades, **se o professor ja tiver lancado no SIGAA**.

Toda sexta-feira as 08:00, ele envia um e-mail de resumo com faltas e media atual de cada materia (`python -m bot_faculdade weekly-report`).

### Formula de calculo da media

Como cada materia usa uma formula diferente (definida no plano de ensino), a formula de cada uma fica configurada em:

```text
config/grade_formulas.json
```

Cada materia define suas unidades (`N1`, `N2`, ...) e os componentes de cada unidade, com peso e (opcionalmente) a data da avaliacao:

```json
{
  "NOME DA MATERIA": {
    "units": [
      {
        "name": "N1",
        "components": [
          {"key": "trabalho1", "label": "Nota do Trabalho da Unidade 1", "weight": 0.3, "due_date": "2026-05-14"},
          {"key": "aval1", "label": "Nota da Avaliacao 1", "weight": 0.7, "due_date": "2026-05-14"}
        ]
      }
    ]
  }
}
```

Para adicionar uma nova materia, mande o plano de ensino/slide com a formula de avaliacao para o Claude Code configurar essa entrada.

### Quando a nota nao aparece no SIGAA

Se `GRADE_REQUEST_DAYS_AFTER` dias (padrao `7`) se passarem apos a data da avaliacao e a nota continuar vazia no SIGAA, o bot manda um e-mail perguntando o valor. Para responder, basta preencher os campos indicados no corpo do e-mail, mantendo o formato `chave: valor` (ex: `aval1: 8.5`), e responder o e-mail.

Se voce nao responder, ele manda **um lembrete** apos mais `GRADE_FOLLOWUP_DAYS_AFTER` dias (padrao `7`).

### Quando a data de uma avaliacao nao esta na configuracao

Algumas materias tem componentes (`trabalho_final`, `apresentacao`, etc.) sem uma data fixa no plano de ensino. Quando aparece uma atividade nova no SIGAA/Classroom para essas materias, o bot manda um e-mail perguntando a qual componente da formula ela corresponde. Responda com o formato:

```text
resposta: nome_do_componente
```

(ou `resposta: nenhum` se a atividade nao for nenhuma das notas da formula). A partir dai, o bot passa a saber a data automaticamente e usa o mesmo prazo de `GRADE_REQUEST_DAYS_AFTER` dias para perguntar a nota.

## WhatsApp (avisos de alta prioridade)

O EVA manda no WhatsApp **so** o que e de alta prioridade (prova, prazo final, edital, matricula, cancelado/adiado, urgente): alertas urgentes, lembretes de prazo (um por item a cada rodada, o mais proximo) e mudancas nesses itens. O resto continua so por e-mail.

Usa a Cloud API da Meta com **template aprovado** (texto livre falha em silencio fora da janela de 24h). Preencha no `.env`:

```text
WHATSAPP_API_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_TO=5564999999999
WHATSAPP_TEMPLATE_NAME=aviso_bot
WHATSAPP_TEMPLATE_LANGUAGE=pt_BR
WHATSAPP_TEMPLATE_PARAMS="EVA (faculdade)|{mensagem}"
```

`WHATSAPP_TEMPLATE_PARAMS` lista o valor de cada variavel do template, separadas por `|`; `{mensagem}` vira o texto do aviso. Teste com:

```powershell
python -m bot_faculdade whatsapp-test
```

A API aceitar a mensagem nao garante a entrega: confira se ela chegou no celular.

## Agendar no Windows

Depois que o `.env` estiver configurado e um teste funcionar, crie uma tarefa no Agendador de Tarefas do Windows para rodar diariamente:

Programa:

```text
F:\INTELIGÊNCIA ARTIFICIAL\EVA\.venv\Scripts\python.exe
```

Argumentos:

```text
-m bot_faculdade sync --notify
```

Se quiser resumo diario em outro horario, crie outra tarefa:

```text
-m bot_faculdade summary
```

Iniciar em:

```text
F:\INTELIGÊNCIA ARTIFICIAL\EVA
```

Ou use o script pronto, que ja cria as tarefas rodando em segundo plano (sem abrir janela):

```powershell
.\scripts\install_windows_tasks.ps1 -InstallDashboard -InstallWeeklyReport
```

Isso cria: sync a cada 30 minutos (e no login), dashboard local sempre ativo, e o resumo semanal de faltas/medias toda sexta-feira as 08:00.

## Ajuste do SIGAA

Cada universidade pode personalizar o SIGAA. O arquivo `src/bot_faculdade/sigaa.py` usa seletores comuns e tambem captura textos da pagina. Se sua tela tiver nomes diferentes, rode com:

```powershell
python -m bot_faculdade sync --only-sigaa --debug-browser
```

Assim voce consegue ver a pagina aberta e ajustar os seletores no codigo.
