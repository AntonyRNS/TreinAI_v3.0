"""Dialogo de identidade NOSTR reutilizado por client_gui.py e server_gui.py: carrega
a chave (nsec) a partir da variavel de ambiente / `.env` (ver nostr_auth.py) e, uma
vez carregada, coleta o relay e o id do grupo (NIP-29) declarados pelo usuario. Se
`require_membership=True` (usado pelo cliente), ao confirmar o grupo o dialogo checa
na hora se essa chave ja esta cadastrada (adicionada por um admin) nesse grupo antes
de liberar a janela principal."""
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from async_worker import AsyncTask
from nostr_auth import DEFAULT_ENV_VAR, AppIdentity, load_identity_from_env
from nostr_groups import check_membership


class NostrLoginDialog(QDialog):
    """Ao fechar com Accepted, expoe `identity`, `relay_url` e `group_id`."""

    def __init__(self, env_var: str = DEFAULT_ENV_VAR, require_membership: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Identidade NOSTR")
        self.env_var = env_var
        self.require_membership = require_membership
        self.identity: Optional[AppIdentity] = None
        self.relay_url: str = ""
        self.group_id: str = ""
        self._task: Optional[AsyncTask] = None

        self.identity_label = QLabel("")
        self.identity_label.setWordWrap(True)
        retry_button = QPushButton("Tentar novamente")
        retry_button.clicked.connect(self._load_identity)

        self.relay_input = QLineEdit()
        self.relay_input.setPlaceholderText("wss://relay.exemplo.com")
        self.group_input = QLineEdit()
        self.group_input.setPlaceholderText("id do grupo (NIP-29)")
        self.group_status = QLabel("")
        self.group_status.setWordWrap(True)
        self.confirm_button = QPushButton("Confirmar")
        self.confirm_button.clicked.connect(self._confirm)

        form = QFormLayout()
        form.addRow("Relay:", self.relay_input)
        form.addRow("Group ID:", self.group_input)

        layout = QVBoxLayout()
        layout.addWidget(self.identity_label)
        layout.addWidget(retry_button)
        layout.addLayout(form)
        layout.addWidget(self.group_status)
        layout.addWidget(self.confirm_button)
        self.setLayout(layout)
        self.resize(380, 280)

        self._load_identity()

    def _load_identity(self):
        try:
            self.identity = load_identity_from_env(self.env_var)
        except Exception as exc:
            self.identity = None
            self.identity_label.setText(f"Falha ao carregar identidade: {exc}")
        else:
            self.identity_label.setText(f"Logado como: {self.identity.pubkey_hex}")

    def _confirm(self):
        if self.identity is None:
            QMessageBox.critical(
                self,
                "Identidade nao carregada",
                f"Defina a variavel de ambiente {self.env_var} (ou o arquivo .env) "
                f"com a nsec e clique em 'Tentar novamente'.",
            )
            return
        relay_url = self.relay_input.text().strip()
        group_id = self.group_input.text().strip()
        if not relay_url or not group_id:
            QMessageBox.warning(self, "Dados incompletos", "Informe o relay e o id do grupo.")
            return

        if not self.require_membership:
            self.relay_url = relay_url
            self.group_id = group_id
            self.accept()
            return

        self.confirm_button.setEnabled(False)
        self.group_status.setText("Verificando associacao ao grupo...")
        self._task = AsyncTask(lambda: check_membership(relay_url, group_id, self.identity.pubkey_hex))
        self._task.succeeded.connect(lambda is_member: self._on_membership_checked(relay_url, group_id, is_member))
        self._task.failed.connect(self._on_membership_check_failed)
        self._task.start()

    def _on_membership_checked(self, relay_url: str, group_id: str, is_member: bool):
        self.confirm_button.setEnabled(True)
        if not is_member:
            self.group_status.setText("Chave nao cadastrada nesse grupo ainda.")
            QMessageBox.warning(
                self, "Nao autorizado", "Aguardando ser adicionado ao grupo pelo administrador."
            )
            return
        self.group_status.setText("")
        self.relay_url = relay_url
        self.group_id = group_id
        self.accept()

    def _on_membership_check_failed(self, message: str):
        self.confirm_button.setEnabled(True)
        self.group_status.setText("")
        QMessageBox.critical(self, "Erro ao verificar associacao", message)
