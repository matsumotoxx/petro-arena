# Integração com Google Sheets

- Pré-requisitos
  - Crie um projeto no Google Cloud.
  - Ative a API Google Sheets.
  - Crie credenciais:
    - Conta de serviço (recomendado para servidor) OU OAuth Client (Desktop).
  - Compartilhe a planilha com:
    - Conta de serviço: e-mail da conta com permissão Editor.
    - OAuth: usuário autenticado com acesso à planilha.

- Configuração de credenciais
  - Conta de serviço via Streamlit Secrets:
    - .streamlit/secrets.toml:
      [gcp_service_account]
      type = "service_account"
      project_id = "..."
      private_key_id = "..."
      private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
      client_email = "svc@proj.iam.gserviceaccount.com"
      client_id = "..."
      token_uri = "https://oauth2.googleapis.com/token"
  - OAuth 2.0:
    - Coloque client_secret.json no diretório do app.
    - Em secrets:
      gcp_oauth_client_secret_path = "client_secret.json"
      gcp_oauth_token_path = "token.json"

- Estrutura de planilhas
  - Abas recomendadas:
    - users: id, username, email, role, balance, created_at
    - transactions: id, user_id, type, amount, description, timestamp
    - missions: id, title, description, reward, deadline, requirements, status
  - Tipos:
    - id/user_id: inteiro
    - valores numéricos: inteiro/float
    - datas: ISO 8601
    - status/type: texto controlado

- Uso no código
  - from components.google_sheets_client import read_rows, append_rows, update_row_by_key, delete_row_by_key
  - Exemplo:
    - dados = read_rows("<SPREADSHEET_ID>", "users")
    - append_rows("<SPREADSHEET_ID>", "users", [[10, "Alice", "a@x", "Jogador", 0, "2026-02-19"]])
    - update_row_by_key("<SPREADSHEET_ID>", "users", "id", 10, {"balance": 50})
    - delete_row_by_key("<SPREADSHEET_ID>", "users", "id", 10)

- Cache e performance
  - Leituras são cacheadas por 60s com st.cache_data.
  - Invalide cache após escritas se necessário.

- Tratamento de erros
  - Sem credenciais: RuntimeError.
  - Falhas de conexão: exceções do client.
  - Colunas ausentes: update/delete retornam False.

- Permissões de compartilhamento
  - Acesse a planilha > Compartilhar.
  - Adicione o e-mail da conta de serviço como Editor.
  - Para OAuth, garanta que o usuário autenticado tem acesso à planilha.
