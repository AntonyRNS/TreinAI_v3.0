"""Interface grafica do cliente (PyQt6): login/senha, endereco do servidor, selecao de dados
e controle do treinamento (Iniciar/Parar) sem travar a aplicacao."""
import sys
import threading
from typing import Optional

import flwr as fl
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
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

from client_logic import FlowerNumPyClient
from model import ClassDirectoryError


class FlowerClientWorker(QThread):
    """Executa o ciclo de vida do cliente Flower em segundo plano, sem travar a GUI."""

    status_changed = pyqtSignal(str)
    metrics_received = pyqtSignal(dict)
    training_finished = pyqtSignal()
    training_failed = pyqtSignal(str)

    def __init__(self, login: str, senha: str, server_address: str, data_dir: str,
                 cancel_event: threading.Event, parent=None):
        super().__init__(parent)
        self.login = login
        self.senha = senha
        self.server_address = server_address
        self.data_dir = data_dir
        self.cancel_event = cancel_event

    def run(self):
        try:
            self.status_changed.emit("Carregando dados e construindo o modelo...")
            client = FlowerNumPyClient(
                login=self.login,
                senha=self.senha,
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
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TreinAI - Cliente")
        self.cancel_event = threading.Event()
        self.data_dir = ""
        self.worker: Optional[FlowerClientWorker] = None

        self.login_input = QLineEdit()
        self.senha_input = QLineEdit()
        self.senha_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.server_input = QLineEdit("127.0.0.1:8080")
        self.dir_label = QLabel("Nenhuma pasta selecionada")
        self.select_dir_button = QPushButton("Selecionar Pasta de Imagens")
        self.start_button = QPushButton("Iniciar Treinamento")
        self.stop_button = QPushButton("Parar Treinamento")
        self.stop_button.setEnabled(False)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)

        form = QFormLayout()
        form.addRow("Login:", self.login_input)
        form.addRow("Senha:", self.senha_input)
        form.addRow("Servidor (IP:porta):", self.server_input)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(self.select_dir_button)
        layout.addWidget(self.dir_label)
        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(self.log_view)
        self.setLayout(layout)

        self.select_dir_button.clicked.connect(self._select_directory)
        self.start_button.clicked.connect(self._start_training)
        self.stop_button.clicked.connect(self._stop_training)

    def _select_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Selecionar pasta de imagens")
        if directory:
            self.data_dir = directory
            self.dir_label.setText(directory)

    def _start_training(self):
        if not self.login_input.text() or not self.senha_input.text():
            QMessageBox.warning(self, "Credenciais ausentes", "Informe login e senha.")
            return
        if not self.server_input.text():
            QMessageBox.warning(self, "Servidor ausente", "Informe o endereco IP/porta do servidor.")
            return
        if not self.data_dir:
            QMessageBox.warning(self, "Pasta nao selecionada", "Selecione a pasta de imagens antes de iniciar.")
            return

        self.cancel_event.clear()
        self.worker = FlowerClientWorker(
            login=self.login_input.text(),
            senha=self.senha_input.text(),
            server_address=self.server_input.text(),
            data_dir=self.data_dir,
            cancel_event=self.cancel_event,
        )
        self.worker.status_changed.connect(self._log)
        self.worker.metrics_received.connect(self._log_metrics)
        self.worker.training_finished.connect(self._on_finished)
        self.worker.training_failed.connect(self._on_failed)
        self.worker.start()

        self.start_button.setEnabled(False)
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
    window = ClientWindow()
    window.resize(480, 480)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
