"""Interface grafica do servidor (PyQt6): porta/IP de escuta, logs de conexao e controle do servico.
Sem campo de hash: a autenticacao e automatica via AuthClientManager (server_logic.py)."""
import sys
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from server_logic import run_server


class FlowerServerWorker(QThread):
    """Roda flwr.server.start_server em segundo plano, sem bloquear a GUI do servidor."""

    status_changed = pyqtSignal(str)
    server_finished = pyqtSignal()
    server_failed = pyqtSignal(str)

    def __init__(self, server_address: str, num_rounds: int = 3, min_clients: int = 2, parent=None):
        super().__init__(parent)
        self.server_address = server_address
        self.num_rounds = num_rounds
        self.min_clients = min_clients

    def run(self):
        try:
            self.status_changed.emit(f"Servidor escutando em {self.server_address}...")
            run_server(self.server_address, num_rounds=self.num_rounds, min_clients=self.min_clients)
            self.server_finished.emit()
        except Exception as exc:  # encaminha qualquer falha para a GUI sem derruba-la
            self.server_failed.emit(str(exc))


class ServerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TreinAI - Servidor Central")
        self.worker: Optional[FlowerServerWorker] = None

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

        self.worker = FlowerServerWorker(
            server_address=self.address_input.text(),
            num_rounds=num_rounds,
            min_clients=min_clients,
        )
        self.worker.status_changed.connect(self._log)
        self.worker.server_finished.connect(
            lambda: self._log("Treinamento federado concluido; modelo global salvo em cnn_model.keras.")
        )
        self.worker.server_failed.connect(lambda msg: self._log(f"Falha no servidor: {msg}"))
        self.worker.start()
        self.start_button.setEnabled(False)

    def _log(self, message: str):
        self.log_view.appendPlainText(message)


def main():
    app = QApplication(sys.argv)
    window = ServerWindow()
    window.resize(480, 360)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
