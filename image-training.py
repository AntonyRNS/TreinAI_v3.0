import tensorflow as tf
from tensorflow.keras import layers, models
import matplotlib.pyplot as plt
from datetime import datetime

# 1. Carregar o dataset a partir da pasta local (estrutura: train/<classe>/*.jpg, test/<classe>/*.jpg)
DATA_DIR = r"C:\Users\Antony\Downloads\CIFAR-10-images-master\CIFAR-10-images"
IMG_SIZE = (32, 32)
BATCH_SIZE = 64

train_ds = tf.keras.utils.image_dataset_from_directory(
    f"{DATA_DIR}\\train",
    image_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    label_mode='int',
    shuffle=True,
    seed=123,
)

test_ds = tf.keras.utils.image_dataset_from_directory(
    f"{DATA_DIR}\\test",
    image_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    label_mode='int',
    shuffle=False,
)

class_names = train_ds.class_names
print("Classes:", class_names)

# 2. Normalizar os pixels para o intervalo [0, 1] e otimizar o pipeline
normalization_layer = layers.Rescaling(1. / 255)
AUTOTUNE = tf.data.AUTOTUNE

train_ds = train_ds.map(lambda x, y: (normalization_layer(x), y)).cache().prefetch(AUTOTUNE)
test_ds = test_ds.map(lambda x, y: (normalization_layer(x), y)).cache().prefetch(AUTOTUNE)

# 3. Construir o modelo CNN
model = models.Sequential([
    layers.Conv2D(32, (3, 3), activation='relu', input_shape=(32, 32, 3)),
    layers.MaxPooling2D((2, 2)),

    layers.Conv2D(64, (3, 3), activation='relu'),
    layers.MaxPooling2D((2, 2)),

    layers.Conv2D(64, (3, 3), activation='relu'),

    layers.Flatten(),
    layers.Dense(64, activation='relu'),
    layers.Dense(len(class_names), activation='softmax')
])

model.summary()

# 4. Compilar o modelo
model.compile(optimizer='adam',
              loss='sparse_categorical_crossentropy',
              metrics=['accuracy'])

# 5. Treinar o modelo
history = model.fit(train_ds, epochs=10, validation_data=test_ds)

# 6. Avaliar o modelo no conjunto de teste
test_loss, test_acc = model.evaluate(test_ds, verbose=2)
print(f"\nAcurácia no teste: {test_acc:.4f}")

# 6.1 Salvar os resultados do treinamento em results.txt
with open('results.txt', 'a', encoding='utf-8') as f:
    f.write(f"===== Treinamento em {datetime.now():%Y-%m-%d %H:%M:%S} =====\n")
    f.write(f"Épocas: {len(history.history['accuracy'])}\n")
    for epoch, (acc, loss, val_acc, val_loss) in enumerate(zip(
            history.history['accuracy'],
            history.history['loss'],
            history.history['val_accuracy'],
            history.history['val_loss']), start=1):
        f.write(f"Época {epoch}: accuracy={acc:.4f} - loss={loss:.4f} - "
                f"val_accuracy={val_acc:.4f} - val_loss={val_loss:.4f}\n")
    f.write(f"Resultado final no teste: accuracy={test_acc:.4f} - loss={test_loss:.4f}\n\n")

# 7. Plotar a evolução da acurácia durante o treinamento
plt.plot(history.history['accuracy'], label='acurácia (treino)')
plt.plot(history.history['val_accuracy'], label='acurácia (validação)')
plt.xlabel('Época')
plt.ylabel('Acurácia')
plt.ylim([0, 1])
plt.legend(loc='lower right')
plt.show()

# 8. Salvar o modelo treinado
model.save('cnn_model.keras')
