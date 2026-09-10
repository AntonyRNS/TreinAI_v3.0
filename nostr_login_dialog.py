"""Dialogo de login NOSTR (NIP-46) reutilizado por client_gui.py e server_gui.py:
conecta a um bunker remoto (colando bunker://... ou escaneando um QR nostrconnect://...)
e, apos autenticado, coleta o relay e o id do grupo (NIP-29) declarados pelo usuario."""
from typing import Optional

import qrcode
from PIL.ImageQt import ImageQt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from async_worker import AsyncTask
from nostr_auth import AppIdentity, await_nostrconnect, build_nostrconnect_uri, connect_bunker
from nostr_sdk import Keys

DEFAULT_PAIRING_RELAY = "wss://relay.nsec.app"


class NostrLoginDialog(QDialog):
    """Ao fechar com Accepted, expoe `identity`, `relay_url` e `group_id`."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login NOSTR (NIP-46)")
        self.identity: Optional[AppIdentity] = None
        self.relay_url: str = ""
        self.group_id: str = ""

        self._task: Optional[AsyncTask] = None
        self._app_keys: Optional[Keys] = None
        self._qr_image = None  # mantem referencia forte enquanto o QPixmap existir

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_login_page())
        self.stack.addWidget(self._build_group_page())

        layout = QVBoxLayout()
        layout.addWidget(self.stack)
        self.setLayout(layout)
        self.resize(420, 440)

    def _build_login_page(self) -> QWidget:
        page = QWidget()
        tabs = QTabWidget()

        bunker_tab = QWidget()
        self.bunker_input = QLineEdit()
        self.bunker_input.setPlaceholderText("bunker://...")
        bunker_connect_btn = QPushButton("Conectar")
        bunker_connect_btn.clicked.connect(self._connect_bunker)
        bunker_layout = QVBoxLayout()
        bunker_layout.addWidget(QLabel("Cole a connection string do seu signer:"))
        bunker_layout.addWidget(self.bunker_input)
        bunker_layout.addWidget(bunker_connect_btn)
        bunker_layout.addStretch(1)
        bunker_tab.setLayout(bunker_layout)

        qr_tab = QWidget()
        self.qr_relay_input = QLineEdit(DEFAULT_PAIRING_RELAY)
        self.qr_label = QLabel("Clique em 'Gerar QR' para iniciar.")
        self.qr_label.setMinimumSize(220, 220)
        self.qr_label.setWordWrap(True)
        qr_generate_btn = QPushButton("Gerar QR")
        qr_generate_btn.clicked.connect(self._start_nostrconnect)
        qr_layout = QVBoxLayout()
        qr_layout.addWidget(QLabel("Relay de pareamento:"))
        qr_layout.addWidget(self.qr_relay_input)
        qr_layout.addWidget(self.qr_label)
        qr_layout.addWidget(qr_generate_btn)
        qr_tab.setLayout(qr_layout)

        tabs.addTab(bunker_tab, "Colar bunker://")
        tabs.addTab(qr_tab, "QR nostrconnect://")

        self.login_status = QLabel("")

        layout = QVBoxLayout()
        layout.addWidget(tabs)
        layout.addWidget(self.login_status)
        page.setLayout(layout)
        return page

    def _build_group_page(self) -> QWidget:
        page = QWidget()
        self.identity_label = QLabel("")
        self.identity_label.setWordWrap(True)
        self.relay_input = QLineEdit()
        self.relay_input.setPlaceholderText("wss://relay.exemplo.com")
        self.group_input = QLineEdit()
        self.group_input.setPlaceholderText("id do grupo (NIP-29)")
        confirm_btn = QPushButton("Confirmar")
        confirm_btn.clicked.connect(self._confirm_group)

        form = QFormLayout()
        form.addRow("Relay:", self.relay_input)
        form.addRow("Group ID:", self.group_input)

        layout = QVBoxLayout()
        layout.addWidget(self.identity_label)
        layout.addLayout(form)
        layout.addWidget(confirm_btn)
        layout.addStretch(1)
        page.setLayout(layout)
        return page

    def _connect_bunker(self):
        bunker_uri = self.bunker_input.text().strip()
        if not bunker_uri:
            QMessageBox.warning(self, "URI ausente", "Cole a connection string bunker://...")
            return
        self.login_status.setText("Conectando ao bunker...")
        self._task = AsyncTask(lambda: connect_bunker(bunker_uri))
        self._task.succeeded.connect(self._on_login_ok)
        self._task.failed.connect(self._on_login_failed)
        self._task.start()

    def _start_nostrconnect(self):
        relay_url = self.qr_relay_input.text().strip()
        if not relay_url:
            QMessageBox.warning(self, "Relay ausente", "Informe o relay de pareamento.")
            return
        self._app_keys = Keys.generate()
        uri = build_nostrconnect_uri(relay_url, self._app_keys)
        self._show_qr(uri)
        self.login_status.setText("Aguardando aprovacao do signer remoto...")
        self._task = AsyncTask(lambda: await_nostrconnect(uri, self._app_keys))
        self._task.succeeded.connect(self._on_login_ok)
        self._task.failed.connect(self._on_login_failed)
        self._task.start()

    def _show_qr(self, uri: str):
        image = qrcode.make(uri).convert("RGB")
        self._qr_image = ImageQt(image)
        pixmap = QPixmap.fromImage(self._qr_image)
        self.qr_label.setPixmap(pixmap.scaled(220, 220))

    def _on_login_ok(self, identity: AppIdentity):
        self.identity = identity
        self.login_status.setText("")
        self.identity_label.setText(f"Logado como: {identity.pubkey_hex}")
        self.stack.setCurrentIndex(1)

    def _on_login_failed(self, message: str):
        self.login_status.setText("")
        QMessageBox.critical(self, "Falha no login NOSTR", message)

    def _confirm_group(self):
        relay_url = self.relay_input.text().strip()
        group_id = self.group_input.text().strip()
        if not relay_url or not group_id:
            QMessageBox.warning(self, "Dados incompletos", "Informe o relay e o id do grupo.")
            return
        self.relay_url = relay_url
        self.group_id = group_id
        self.accept()
