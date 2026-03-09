# Análise e Sugestões de Melhorias - Petro Arena

## 1. Segurança

### Estado Atual
- **Senhas**: Armazenadas com hash SHA-256 (implementação básica em `database.py`).
- **Sessão**: Implementada persistência via cookies (7 dias) e `st.session_state`.
- **SQL Injection**: Uso correto de parâmetros em queries (`?` no SQLite).
- **Controle de Acesso**: Verificações de role (`Administrador` vs `Jogador`) nas rotas principais.

### Sugestões
- **Hashing Robusto**: Migrar de SHA-256 simples para `bcrypt` ou `argon2` (biblioteca `bcrypt` ou `passlib`) para proteção contra ataques de rainbow table e força bruta.
- **Validação de Senha**: Implementar requisitos mínimos (comprimento, caracteres especiais) no registro e redefinição.
- **CSRF**: Streamlit gerencia parte disso, mas para uma aplicação gamificada sensível (pontos = dinheiro/prêmios?), considerar tokens adicionais para transações críticas.

## 2. Performance e Escalabilidade

### Estado Atual
- **Banco de Dados**: SQLite. Excelente para prototipagem e uso local/pequeno porte.
- **Concorrência**: SQLite tem limitações de escrita simultânea ("database is locked").
- **Frontend**: `st.rerun()` é usado frequentemente para atualizar o estado após ações.

### Sugestões
- **Migração de DB**: Para produção multiusuário, migrar para PostgreSQL ou MySQL. O código usa SQL padrão, facilitando a transição (usando SQLAlchemy ou adaptando `database.py`).
- **Cache**: Implementar `st.cache_data` para queries pesadas (ex: logs de auditoria, ranking histórico) para reduzir carga no DB.
- **Paginação**: Adicionar paginação nas tabelas de Auditoria e Extrato, que tendem a crescer indefinidamente.

## 3. Experiência do Usuário (UX/UI)

### Estado Atual
- **Gamificação**: Visual "Cyberpunk/Neon" atrativo e imersivo.
- **Responsividade**: Layouts flexíveis (grids e colunas) funcionam bem.
- **Feedback**: Uso de Toasts e mensagens de sucesso/erro.

### Sugestões
- **Dashboard Personalizado**: Permitir que usuários escolham temas ou "Skins" (Neon Verde, Neon Roxo, Cyberpunk Amarelo).
- **Notificações Real-Time**: Implementar polling silencioso ou WebSockets (mais complexo no Streamlit) para atualizar notificações sem recarregar a página inteira.
- **Avatar Upload**: Permitir upload de imagem de perfil real em vez de apenas ícones genéricos.

## 4. Funcionalidades Competitivas (Novas Features)

### Sugestões para Futuro

5.  **Badges Especiais**: Medalhas por feitos específicos (ex: "Primeira Compra", "Top 1 do Mês") além do nível por pontos.

## 5. Qualidade de Código

### Estado Atual
- **Estrutura**: `app.py` monolítico (~900 linhas).
- **Testes**: Testes de integração básicos cobrindo fluxo crítico.

### Sugestões
- **Refatoração**: Separar `app.py` em módulos: `views/admin.py`, `views/player.py`, `components/cards.py`.
- **Typing**: Adicionar Type Hints em todas as funções para melhor manutenibilidade.
- **CI/CD**: Configurar pipeline para rodar testes automaticamente em Pull Requests.
