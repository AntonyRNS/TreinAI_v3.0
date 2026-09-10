"""Interface grafica do servidor (PyQt6): identidade NOSTR (chave lida de variavel de
ambiente/.env), relay/grupo NIP-29 (publica o endereco de escuta no grupo e autoriza
clientes pela associacao atual ao grupo), logs de conexao e controle do servico."""
import asyncio
import sys
import threading
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from async_worker import AsyncTask
from nostr_auth import AppIdentity
from nostr_groups import publish_server_address, watch_membership
from nostr_login_dialog import NostrLoginDialog
from server_logic import run_server


class MembershipWatcher(QThread):
    """Mantem, em segundo plano, o conjunto de pubkeys NOSTR atualmente membros do
    grupo NIP-29 declarado; consultada de forma sincrona (sem I/O de rede) por
    AggregationStrategy a cada handshake de cliente (ver server_logic.py)."""

    def __init__(self, relay_url: str, group_id: str, parent=None):
        super().__init__(parent)
        self.relay_url = relay_url
        self.group_id = group_id
        self._lock = threading.Lock()
        self._authorized: set[str] = set()
        self._latest_at: dict[str, int] = {}
        self._stop_event = threading.Event()

    def is_authorized(self, pubkey_hex: str) -> bool:
        with self._lock:
            return pubkey_hex in self._authorized

    def stop(self):
        self._stop_event.set()

    def _on_update(self, pubkey_hex: str, is_member: bool, created_at: int):
        with self._lock:
            if self._latest_at.get(pubkey_hex, -1) > created_at:
                return
            self._latest_at[pubkey_hex] = created_at
            if is_member:
                self._authorized.add(pubkey_hex)
            else:
                self._authorized.discard(pubkey_hex)

    def run(self):
        asyncio.run(watch_membership(self.relay_url, self.group_id, self._on_update, self._stop_event.is_set))


class FlowerServerWorker(QThread):
    """Roda flwr.server.start_server em segundo plano, sem bloquear a GUI do servidor."""

    status_changed = pyqtSignal(str)
    server_finished = pyqtSignal()
    server_failed = pyqtSignal(str)

    def __init__(self, server_address: str, membership_watcher: MembershipWatcher,
                 num_rounds: int = 3, min_clients: int = 2, parent=None):
        super().__init__(parent)
        self.server_address = server_address
        self.membership_watcher = membership_watcher
        self.num_rounds = num_rounds
        self.min_clients = min_clients

    def run(self):
        try:
            self.status_changed.emit(f"Servidor escutando em {self.server_address}...")
            run_server(
                self.server_address,
                membership_watcher=self.membership_watcher,
                num_rounds=self.num_rounds,
                min_clients=self.min_clients,
            )
            self.server_finished.emit()
        except Exception as exc:  # encaminha qualquer falha para a GUI sem derruba-la
            self.server_failed.emit(str(exc))


class ServerWindow(QWidget):
    def __init__(self, identity: AppIdentity, relay_url: str, group_id: str):
        super().__init__()
        self.setWindowTitle("TreinAI - Servidor Central")
        self.identity = identity
        self.relay_url = relay_url
        self.group_id = group_id
        self.worker: Optional[FlowerServerWorker] = None
        self.membership_watcher: Optional[MembershipWatcher] = None
        self._task: Optional[AsyncTask] = None

        self.identity_label = QLabel(f"Logado como: {identity.pubkey_hex}")
        self.identity_label.setWordWrap(True)
        self.group_label = QLabel(f"Grupo: {group_id} @ {relay_url}")
        self.group_label.setWordWrap(True)
        self.address_input = QLineEdit("0.0.0.0:8080")
        self.rounds_input = QLineEdit("3")
        self.min_clients_input = QLineEdit("2")
        self.start_button = QPushButton("Iniciar Servidor")
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)

        form = QFormLayout()
        form.addRow("Endereco (IP:porta):", self.address_input)
        form.addRow("Rodadas (FedAvg):", self.rounds_input)
        form.addRow("Minimo de clientes:", self.min_clients_input)

        layout = QVBoxLayout()
        layout.addWidget(self.identity_label)
        layout.addWidget(self.group_label)
        layout.addLayout(form)
        layout.addWidget(self.start_button)
        layout.addWidget(self.log_view)
        self.setLayout(layout)

        self.start_button.clicked.connect(self._start_server)

    def _start_server(self):
        try:
            num_rounds = int(self.rounds_input.text())
            min_clients = int(self.min_clients_input.text())
        except ValueError:
            QMessageBox.warning(self, "Valor invalido", "Rodadas e minimo de clientes devem ser numeros inteiros.")
            return

        address = self.address_input.text()
        self.start_button.setEnabled(False)
        self._log("Publicando endereco do servidor no grupo...")
        self._task = AsyncTask(
            lambda: publish_server_address(self.relay_url, self.identity.signer, self.group_id, address)
        )
        self._task.succeeded.connect(lambda _: self._launch_server(address, num_rounds, min_clients))
        self._task.failed.connect(self._on_publish_failed)
        self._task.start()

    def _on_publish_failed(self, message: str):
        self.start_button.setEnabled(True)
        QMessageBox.critical(self, "Falha ao publicar no grupo", message)

    def _launch_server(self, address: str, num_rounds: int, min_clients: int):
        self._log("Endereco publicado no grupo.")
        self.membership_watcher = MembershipWatcher(self.relay_url, self.group_id)
        self.membership_watcher.start()

        self.worker = FlowerServerWorker(
            server_address=address,
            membership_watcher=self.membership_watcher,
            num_rounds=num_rounds,
            min_clients=min_clients,
        )
        self.worker.status_changed.connect(self._log)
        self.worker.server_finished.connect(
            lambda: self._log("Treinamento federado concluido; modelo global salvo em cnn_model.keras.")
        )
        self.worker.server_failed.connect(lambda msg: self._log(f"Falha no servidor: {msg}"))
        self.worker.start()

    def _log(self, message: str):
        self.log_view.appendPlainText(message)

    def closeEvent(self, event):
        if self.membership_watcher is not None:
            self.membership_watcher.stop()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)

    login_dialog = NostrLoginDialog()
    if login_dialog.exec() != QDialog.DialogCode.Accepted or login_dialog.identity is None:
        sys.exit(0)

    window = ServerWindow(login_dialog.identity, login_dialog.relay_url, login_dialog.group_id)
    window.resize(480, 420)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
