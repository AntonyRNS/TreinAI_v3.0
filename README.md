# TreinAI - Treinamento Federado com Flower

Sistema de treinamento federado (servidor + clientes desktop) usando Flower (`flwr`) e uma CNN TensorFlow/Keras. Veja `specs_treinai.md` para a especificação completa da arquitetura.

## 1. Preparar o ambiente

Cada instância (servidor e cada cliente) deve rodar no seu próprio `venv`:

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

## 2. Rodar o servidor

```bash
python server_gui.py
```

Na janela:
- **Endereço (IP:porta):** endereço de escuta (padrão `0.0.0.0:8080`).
- **Rodadas (FedAvg):** número de rounds de agregação federada (padrão `3`).
- **Mínimo de clientes:** quantos clientes precisam se conectar para cada round iniciar (padrão `2`).

Clique em **Iniciar Servidor**. Ao final do treinamento, o modelo global agregado é salvo em `cnn_model.keras`.

## 3. Rodar um cliente

Em outro processo/máquina (com seu próprio `venv` ativo):

```bash
python client_gui.py
```

Na janela:
- **Login / Senha:** uma das credenciais mockadas em `mock_users.json` (ex.: `cientista1` / `treinai@123`).
- **Servidor (IP:porta):** endereço do servidor central (ex.: `127.0.0.1:8080` se estiver na mesma máquina).
- **Selecionar Pasta de Imagens:** diretório local com uma subpasta por classe (nomes e quantidade devem bater exatamente com `CLASS_NAMES` em `model.py`).

Clique em **Iniciar Treinamento** para conectar ao servidor e treinar localmente; **Parar Treinamento** interrompe de forma graciosa ao fim do lote/época atual. As métricas de cada época são gravadas em `results.txt` local ao cliente.

## Observações

- Inicie o servidor antes dos clientes; o round só começa quando o número mínimo de clientes estiver conectado.
- Credenciais inválidas (fora das duas registradas em `mock_users.json`) são rejeitadas no handshake, antes de qualquer treinamento.
- Repita o passo 3 em quantos clientes forem necessários, cada um apontando para o mesmo endereço de servidor.
