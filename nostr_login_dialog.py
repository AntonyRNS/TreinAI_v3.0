"""Dialogo de identidade NOSTR reutilizado por client_gui.py e server_gui.py: o usuario
digita sua chave publica e sua chave privada (login simples provisorio, ver
nostr_auth.login_with_keys, que as guarda de forma volatil em `os.environ`) junto com
o relay e o id do grupo (NIP-29). Se
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
from nostr_auth import AppIdentity, login_with_keys
from nostr_groups import check_membership


class NostrLoginDialog(QDialog):
    """Ao fechar com Accepted, expoe `identity`, `relay_url` e `group_id`."""

    def __init__(self, require_membership: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Identidade NOSTR")
        self.require_membership = require_membership
        self.identity: Optional[AppIdentity] = None
        self.relay_url: str = ""
        self.group_id: str = ""
        self._task: Optional[AsyncTask] = None

        self.pubkey_input = QLineEdit()
        self.pubkey_input.setPlaceholderText("npub1... ou hex")
        self.privkey_input = QLineEdit()
        self.privkey_input.setPlaceholderText("nsec1... ou hex")
        self.privkey_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.relay_input = QLineEdit()
        self.relay_input.setPlaceholderText("wss://relay.exemplo.com")
        self.group_input = QLineEdit()
        self.group_input.setPlaceholderText("id do grupo (NIP-29)")
        self.group_status = QLabel("")
        self.group_status.setWordWrap(True)
        self.confirm_button = QPushButton("Confirmar")
        self.confirm_button.clicked.connect(self._confirm)

        form = QFormLayout()
        form.addRow("Chave publica:", self.pubkey_input)
        form.addRow("Chave privada:", self.privkey_input)
        form.addRow("Relay:", self.relay_input)
        form.addRow("Group ID:", self.group_input)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(self.group_status)
        layout.addWidget(self.confirm_button)
        self.setLayout(layout)
        self.resize(420, 260)

    def _confirm(self):
        try:
            self.identity = login_with_keys(self.pubkey_input.text(), self.privkey_input.text())
        except ValueError as exc:
            self.identity = None
            QMessageBox.critical(self, "Chaves invalidas", str(exc))
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
