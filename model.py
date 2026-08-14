"""Arquitetura da CNN e utilitarios de dados/treino, espelhando image-training.py.

model.py e o modulo unico importado por cliente e servidor: NUM_CLASSES/CLASS_NAMES
sao fixados aqui (nao inferidos por diretorio de cliente) para garantir que a
camada de saida da CNN seja identica em todos os participantes do FedAvg.
"""
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import tensorflow as tf
from tensorflow.keras import layers, models

IMG_SIZE = (32, 32)
INPUT_SHAPE = (32, 32, 3)
BATCH_SIZE = 64

CLASS_NAMES = [
    "airplane", "automobile", "bird", "cat", "deer",
    "dog", "frog", "horse", "ship", "truck",
]
NUM_CLASSES = len(CLASS_NAMES)


def create_cnn_model(num_classes: int = NUM_CLASSES, input_shape: tuple = INPUT_SHAPE) -> tf.keras.Model:
    """Mesma arquitetura definida em image-training.py."""
    model = models.Sequential([
        layers.Conv2D(32, (3, 3), activation="relu", input_shape=input_shape),
        layers.MaxPooling2D((2, 2)),
        layers.Conv2D(64, (3, 3), activation="relu"),
        layers.MaxPooling2D((2, 2)),
        layers.Conv2D(64, (3, 3), activation="relu"),
        layers.Flatten(),
        layers.Dense(64, activation="relu"),
        layers.Dense(num_classes, activation="softmax"),
    ])
    model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    return model


class ClassDirectoryError(ValueError):
    """Diretorio ausente, sem subpastas de classe, ou com classes divergentes de CLASS_NAMES."""


def _assert_class_directories(data_dir: Path) -> None:
    if not data_dir.is_dir():
        raise ClassDirectoryError(f"Diretorio nao encontrado: {data_dir}")

    found = sorted(p.name for p in data_dir.iterdir() if p.is_dir())
    if not found:
        raise ClassDirectoryError(f"Nenhuma subpasta de classe encontrada em: {data_dir}")

    expected = sorted(CLASS_NAMES)
    if found != expected:
        raise ClassDirectoryError(
            "As subpastas de classe encontradas nao correspondem as classes esperadas.\n"
            f"Esperado: {expected}\nEncontrado: {found}"
        )


def load_client_dataset(data_dir: str, validation_split: float = 0.2, seed: int = 123):
    """Carrega imagens reais de um diretorio com uma subpasta por classe.

    Valida a estrutura contra CLASS_NAMES antes de carregar, redimensiona para
    32x32, converte para RGB e normaliza os pixels para [0, 1].
    """
    directory = Path(data_dir)
    _assert_class_directories(directory)

    train_ds = tf.keras.utils.image_dataset_from_directory(
        directory,
        validation_split=validation_split,
        subset="training",
        seed=seed,
        image_size=IMG_SIZE,
        batch_size=BATCH_SIZE,
        label_mode="int",
        color_mode="rgb",
        class_names=CLASS_NAMES,
    )
    val_ds = tf.keras.utils.image_dataset_from_directory(
        directory,
        validation_split=validation_split,
        subset="validation",
        seed=seed,
        image_size=IMG_SIZE,
        batch_size=BATCH_SIZE,
        label_mode="int",
        color_mode="rgb",
        class_names=CLASS_NAMES,
    )

    normalization_layer = layers.Rescaling(1.0 / 255)
    autotune = tf.data.AUTOTUNE
    train_ds = train_ds.map(lambda x, y: (normalization_layer(x), y)).cache().prefetch(autotune)
    val_ds = val_ds.map(lambda x, y: (normalization_layer(x), y)).cache().prefetch(autotune)
    return train_ds, val_ds


def dataset_size(dataset: tf.data.Dataset, batch_size: int = BATCH_SIZE) -> int:
    """Aproxima o numero de exemplos em um dataset ja batchado (usado para ponderar o FedAvg)."""
    cardinality = tf.data.experimental.cardinality(dataset).numpy()
    if cardinality < 0:
        cardinality = sum(1 for _ in dataset)
    return int(cardinality) * batch_size


class StopTrainingCallback(tf.keras.callbacks.Callback):
    """Verifica a threading.Event de cancelamento a cada lote/epoca para interromper o fit graciosamente."""

    def __init__(self, cancel_event: threading.Event):
        super().__init__()
        self._cancel_event = cancel_event

    def on_train_batch_end(self, batch, logs=None):
        if self._cancel_event.is_set():
            self.model.stop_training = True

    def on_epoch_end(self, epoch, logs=None):
        if self._cancel_event.is_set():
            self.model.stop_training = True


def append_results_file(results_path: str, history, test_loss: float, test_acc: float) -> None:
    """Registra loss/accuracy de treino e validacao por epoca em results.txt local ao cliente."""
    with open(results_path, "a", encoding="utf-8") as f:
        f.write(f"===== Treinamento em {datetime.now():%Y-%m-%d %H:%M:%S} =====\n")
        f.write(f"Epocas: {len(history.history.get('accuracy', []))}\n")
        for epoch, (acc, loss, val_acc, val_loss) in enumerate(zip(
                history.history.get("accuracy", []),
                history.history.get("loss", []),
                history.history.get("val_accuracy", []),
                history.history.get("val_loss", []),
        ), start=1):
            f.write(
                f"Epoca {epoch}: accuracy={acc:.4f} - loss={loss:.4f} - "
                f"val_accuracy={val_acc:.4f} - val_loss={val_loss:.4f}\n"
            )
        f.write(f"Resultado final: accuracy={test_acc:.4f} - loss={test_loss:.4f}\n\n")
