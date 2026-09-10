# TreinAI - Treinamento Federado com Flower

Sistema de treinamento federado (servidor + clientes desktop) usando Flower (`flwr`) e uma CNN TensorFlow/Keras. Veja `specs_treinai.md` para a especificação completa da arquitetura.

## 1. Preparar o ambiente

Cada instância (servidor e cada cliente) deve rodar no seu próprio `venv`:

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

## 2. Login NOSTR (NIP-46) e grupo (NIP-29)

Tanto `server_gui.py` quanto `client_gui.py` abrem, ao iniciar, um diálogo de login NOSTR antes de liberar a janela principal:

1. **Autenticação (NIP-46):** conecte-se a um signer remoto (bunker) por um dos dois fluxos:
   - **Colar bunker://** — cole a connection string `bunker://...` já emitida pelo seu signer (ex.: Amber, nsec.app).
   - **QR nostrconnect://** — clique em "Gerar QR" e escaneie o código com o signer remoto para aprovar a conexão.
2. **Relay e grupo (NIP-29):** depois de autenticado, informe o relay (`wss://...`) e o id do grupo NIP-29 aos quais a instância vai se associar. O operador do servidor precisa já ser membro/admin desse grupo; cada cliente precisa ter sido adicionado a ele (evento `kind:9000`) por um admin antes de poder treinar.

## 3. Rodar o servidor

```bash
python server_gui.py
```

Depois do login NOSTR, na janela:
- **Endereço (IP:porta):** endereço de escuta (padrão `0.0.0.0:8080`).
- **Rodadas (FedAvg):** número de rounds de agregação federada (padrão `3`).
- **Mínimo de clientes:** quantos clientes precisam se conectar para cada round iniciar (padrão `2`).

Clique em **Iniciar Servidor**: o endereço é publicado no grupo NIP-29 declarado (para os clientes descobrirem) e a autorização de cada cliente passa a depender de ele estar atualmente associado a esse grupo. Ao final do treinamento, o modelo global agregado é salvo em `cnn_model.keras`.

## 4. Rodar um cliente

Em outro processo/máquina (com seu próprio `venv` ativo):

```bash
python client_gui.py
```

Depois do login NOSTR, na janela:
- **Buscar Servidor:** preenche automaticamente o endereço IP/porta a partir do que o servidor publicou no grupo (o campo continua editável, como alternativa manual).
- **Selecionar Pasta de Imagens:** diretório local com uma subpasta por classe (nomes e quantidade devem bater exatamente com `CLASS_NAMES` em `model.py`).

Clique em **Iniciar Treinamento**: o app confirma que sua chave NOSTR está atualmente associada ao grupo antes de conectar ao servidor e treinar localmente; **Parar Treinamento** interrompe de forma graciosa ao fim do lote/época atual. As métricas de cada época são gravadas em `results.txt` local ao cliente.

## Observações

- Inicie o servidor antes dos clientes; o round só começa quando o número mínimo de clientes estiver conectado.
- Um cliente cuja chave NOSTR não esteja (mais) associada ao grupo é rejeitado no handshake, antes de qualquer treinamento.
- Repita o passo 4 em quantos clientes forem necessários, cada um apontando para o mesmo relay/grupo.
