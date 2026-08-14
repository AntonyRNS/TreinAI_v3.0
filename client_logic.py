"""Cliente Flower: treina a CNN real localmente e participa da agregacao federada (FedAvg)."""
import threading
from typing import Callable, Optional

import flwr as fl

from auth import generate_auth_hash
from model import (
    StopTrainingCallback,
    append_results_file,
    create_cnn_model,
    dataset_size,
    load_client_dataset,
)


class TrainingCancelled(Exception):
    """Levantada quando 'Parar' e acionado antes do inicio de uma rodada local."""


class FlowerNumPyClient(fl.client.NumPyClient):
    def __init__(
        self,
        login: str,
        senha: str,
        data_dir: str,
        cancel_event: threading.Event,
        epochs: int = 5,
        results_path: str = "results.txt",
        on_metrics: Optional[Callable[[dict], None]] = None,
    ):
        self.login = login
        self.senha = senha
        self.cancel_event = cancel_event
        self.epochs = epochs
        self.results_path = results_path
        self.on_metrics = on_metrics

        self.model = create_cnn_model()
        self.train_ds, self.val_ds = load_client_dataset(data_dir)

    def get_properties(self, config):
        # Token de autenticacao enviado ao servidor no handshake (ver auth.py).
        return {"auth_hash": generate_auth_hash(self.login, self.senha)}

    def get_parameters(self, config):
        return self.model.get_weights()

    def fit(self, parameters, config):
        if self.cancel_event.is_set():
            raise TrainingCancelled("Treinamento cancelado antes de iniciar a rodada local.")

        self.model.set_weights(parameters)
        callback = StopTrainingCallback(self.cancel_event)
        history = self.model.fit(
            self.train_ds,
            validation_data=self.val_ds,
            epochs=self.epochs,
            callbacks=[callback],
            verbose=0,
        )

        test_loss, test_acc = self.model.evaluate(self.val_ds, verbose=0)
        append_results_file(self.results_path, history, test_loss, test_acc)

        metrics = {
            "accuracy": float(history.history.get("accuracy", [test_acc])[-1]),
            "val_accuracy": float(test_acc),
            "loss": float(history.history.get("loss", [test_loss])[-1]),
            "val_loss": float(test_loss),
        }
        if self.on_metrics:
            self.on_metrics(metrics)

        return self.model.get_weights(), dataset_size(self.train_ds), metrics

    def evaluate(self, parameters, config):
        self.model.set_weights(parameters)
        loss, accuracy = self.model.evaluate(self.val_ds, verbose=0)
        return float(loss), dataset_size(self.val_ds), {"accuracy": float(accuracy)}
