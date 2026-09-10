"""Interface grafica do cliente (PyQt6): login NOSTR (NIP-46), relay/grupo NIP-29 para
descobrir o endereco do servidor central, selecao de dados e controle do treinamento
(Iniciar/Parar) sem travar a aplicacao."""
import sys
import threading
from typing import Optional

import flwr as fl
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
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
from client_logic import FlowerNumPyClient
from model import ClassDirectoryError
from nostr_auth import AppIdentity
from nostr_groups import check_membership, fetch_server_address
from nostr_login_dialog import NostrLoginDialog


class FlowerClientWorker(QThread):
    """Executa o ciclo de vida do cliente Flower em segundo plano, sem travar a GUI."""

    status_changed = pyqtSignal(str)
    metrics_received = pyqtSignal(dict)
    training_finished = pyqtSignal()
    training_failed = pyqtSignal(str)

    def __init__(self, pubkey_hex: str, server_address: str, data_dir: str,
                 cancel_event: threading.Event, parent=None):
        super().__init__(parent)
        self.pubkey_hex = pubkey_hex
        self.server_address = server_address
        self.data_dir = data_dir
        self.cancel_event = cancel_event

    def run(self):
        try:
            self.status_changed.emit("Carregando dados e construindo o modelo...")
            client = FlowerNumPyClient(
                pubkey_hex=self.pubkey_hex,
                data_dir=self.data_dir,
                cancel_event=self.cancel_event,
                on_metrics=self.metrics_received.emit,
            )
            self.status_changed.emit(f"Conectando ao servidor em {self.server_address}...")
            fl.client.start_numpy_client(server_address=self.server_address, client=client)
            self.training_finished.emit()
        except ClassDirectoryError as exc:
            self.training_failed.emit(str(exc))
        except Exception as exc:  # encaminha qualquer falha do TF/Flower para a GUI sem derruba-la
            self.training_failed.emit(str(exc))


class ClientWindow(QWidget):
    def __init__(self, identity: AppIdentity, relay_url: str, group_id: str):
        super().__init__()
        self.setWindowTitle("TreinAI - Cliente")
        self.identity = identity
        self.relay_url = relay_url
        self.group_id = group_id
        self.cancel_event = threading.Event()
        self.data_dir = ""
        self.worker: Optional[FlowerClientWorker] = None
        self._task: Optional[AsyncTask] = None

        self.identity_label = QLabel(f"Logado como: {identity.pubkey_hex}")
        self.identity_label.setWordWrap(True)
        self.group_label = QLabel(f"Grupo: {group_id} @ {relay_url}")
        self.group_label.setWordWrap(True)
        self.server_input = QLineEdit()
        self.fetch_server_button = QPushButton("Buscar Servidor")
        self.dir_label = QLabel("Nenhuma pasta selecionada")
        self.select_dir_button = QPushButton("Selecionar Pasta de Imagens")
        self.start_button = QPushButton("Iniciar Treinamento")
        self.stop_button = QPushButton("Parar Treinamento")
        self.stop_button.setEnabled(False)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)

        form = QFormLayout()
        form.addRow("Servidor (IP:porta):", self.server_input)

        layout = QVBoxLayout()
        layout.addWidget(self.identity_label)
        layout.addWidget(self.group_label)
        layout.addLayout(form)
        layout.addWidget(self.fetch_server_button)
        layout.addWidget(self.select_dir_button)
        layout.addWidget(self.dir_label)
        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(self.log_view)
        self.setLayout(layout)

        self.fetch_server_button.clicked.connect(self._fetch_server)
        self.select_dir_button.clicked.connect(self._select_directory)
        self.start_button.clicked.connect(self._start_training)
        self.stop_button.clicked.connect(self._stop_training)

    def _fetch_server(self):
        self._log("Buscando endereco do servidor no grupo...")
        self._task = AsyncTask(lambda: fetch_server_address(self.relay_url, self.group_id))
        self._task.succeeded.connect(self._on_server_fetched)
        self._task.failed.connect(lambda msg: self._log(f"Falha ao buscar servidor: {msg}"))
        self._task.start()

    def _on_server_fetched(self, address: Optional[str]):
        if address:
            self.server_input.setText(address)
            self._log(f"Endereco do servidor encontrado: {address}")
        else:
            self._log("Nenhum endereco de servidor publicado nesse grupo ainda.")

    def _select_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Selecionar pasta de imagens")
        if directory:
            self.data_dir = directory
            self.dir_label.setText(directory)

    def _start_training(self):
        if not self.server_input.text():
            QMessageBox.warning(self, "Servidor ausente", "Informe ou busque o endereco IP/porta do servidor.")
            return
        if not self.data_dir:
            QMessageBox.warning(self, "Pasta nao selecionada", "Selecione a pasta de imagens antes de iniciar.")
            return

        self.start_button.setEnabled(False)
        self._log("Verificando associacao ao grupo...")
        self._task = AsyncTask(lambda: check_membership(self.relay_url, self.group_id, self.identity.pubkey_hex))
        self._task.succeeded.connect(self._on_membership_checked)
        self._task.failed.connect(self._on_membership_check_failed)
        self._task.start()

    def _on_membership_check_failed(self, message: str):
        self.start_button.setEnabled(True)
        QMessageBox.critical(self, "Erro ao verificar associacao", message)

    def _on_membership_checked(self, is_member: bool):
        if not is_member:
            self.start_button.setEnabled(True)
            QMessageBox.warning(
                self, "Nao autorizado", "Aguardando ser adicionado ao grupo pelo administrador."
            )
            return
        self._begin_training()

    def _begin_training(self):
        self.cancel_event.clear()
        self.worker = FlowerClientWorker(
            pubkey_hex=self.identity.pubkey_hex,
            server_address=self.server_input.text(),
            data_dir=self.data_dir,
            cancel_event=self.cancel_event,
        )
        self.worker.status_changed.connect(self._log)
        self.worker.metrics_received.connect(self._log_metrics)
        self.worker.training_finished.connect(self._on_finished)
        self.worker.training_failed.connect(self._on_failed)
        self.worker.start()
        self.stop_button.setEnabled(True)

    def _stop_training(self):
        self.cancel_event.set()
        self._log("Cancelamento solicitado. Aguardando o fim da epoca/lote atual...")

    def _log(self, message: str):
        self.log_view.appendPlainText(message)

    def _log_metrics(self, metrics: dict):
        self._log(
            f"accuracy={metrics['accuracy']:.4f} val_accuracy={metrics['val_accuracy']:.4f} "
            f"loss={metrics['loss']:.4f} val_loss={metrics['val_loss']:.4f}"
        )

    def _on_finished(self):
        self._log("Treinamento federado concluido.")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def _on_failed(self, message: str):
        self._log(f"Falha no treinamento: {message}")
        QMessageBox.critical(self, "Erro no treinamento", message)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)


def main():
    app = QApplication(sys.argv)

    login_dialog = NostrLoginDialog()
    if login_dialog.exec() != QDialog.DialogCode.Accepted or login_dialog.identity is None:
        sys.exit(0)

    window = ClientWindow(login_dialog.identity, login_dialog.relay_url, login_dialog.group_id)
    window.resize(480, 560)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
