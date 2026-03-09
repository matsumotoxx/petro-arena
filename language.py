# Dicionário de traduções e textos do sistema
TRANSLATIONS = {
    'EARN': 'Ganho de Pontos',
    'SPEND': 'Gasto de Pontos',
    'PENALTY': 'Penalidade',
    'POINTS_EARN': 'Crédito de Pontos',
    'POINTS_PENALTY': 'Débito de Pontos',
    'COMPLETE_MISSION': 'Missão Concluída',
    'APPROVE_MISSION': 'Missão Aprovada',
    'REJECT_MISSION': 'Missão Rejeitada',
    'REMOVE_AVATAR': 'Remoção de Avatar',
    'DB_RESTORE': 'Restauração de Backup',
    'RESTORE_BACKUP': 'Restauração de Backup',
    'VIEW_EMAIL': 'Visualização de E-mail PII',
    'LOGIN': 'Acesso ao Sistema',
    'LOGOUT': 'Saída do Sistema',
    'CREATE_USER': 'Criação de Usuário',
    'DELETE_USER': 'Exclusão de Usuário',
    'RESET_PASSWORD': 'Redefinição de Senha',
    'ADD_ITEM': 'Novo Item na Loja',
    'DELETE_ITEM': 'Item Removido da Loja',
    'PURCHASE_APPROVE': 'Compra Aprovada',
    'PURCHASE_REJECT': 'Compra Rejeitada',
}

def get_text(key):
    """Retorna a tradução amigável para uma chave técnica."""
    return TRANSLATIONS.get(key, key)
