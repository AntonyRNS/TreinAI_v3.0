# Especificação Técnica Completa: Sistema de Treinamento Federado com Flower.ai

**Versão:** 3.0 (Integração com o modelo TensorFlow/Keras real)  
**Status:** Documento de Engenharia de Software  
**Metodologia:** Desenvolvimento Orientado por Especificações (SDD)  

---

## Fase 1: Especificar

Esta fase define as capacidades e as fronteiras do sistema do ponto de vista funcional e de qualidade, servindo como a única fonte da verdade para a implementação do treinamento federado com dados e modelo reais.

### 1.1. Resumo
O sistema consiste em uma aplicação desktop distribuída para treinamento federado orquestrada pelo framework Flower.ai. A arquitetura é composta por instâncias de cliente e um servidor central rodando em processos distintos, comunicando-se via rede por endereço IP/gRPC. Ao abrir a aplicação e informar login e senha mockados, o cliente calcula automaticamente um hash SHA-256 dessas credenciais, usado como token de autenticação no handshake gRPC — o servidor conhece os mesmos dois registros mockados, recalcula os hashes esperados e só aceita a conexão se houver correspondência exata, sem que nenhum hash precise ser digitado manualmente em qualquer uma das pontas. Cada cliente treina localmente uma CNN real em TensorFlow/Keras usando imagens organizadas em subpastas por classe, grava as métricas de treino em `results.txt` local e envia os parâmetros aprendidos (junto com as mesmas métricas) ao servidor, que agrega as atualizações de múltiplos clientes por meio do algoritmo FedAvg e devolve o modelo global atualizado. São permitidos exclusivamente dois registros mockados de autenticação, contendo login e senha, mantidos em um arquivo de referência separado para fácil consulta em ambiente de teste; imagens, amostras, pesos, métricas e demais dados do treinamento devem ser reais. O número e a identidade das classes de classificação são fixados centralmente (não inferidos por cliente) para garantir que a arquitetura do modelo seja idêntica em todos os participantes da agregação federada.

### 1.2. Histórias do Usuário
* **Como operador do servidor central,** quero utilizar uma interface gráfica (PyQt) para definir a porta/IP de escuta, inicializar o servidor e validar automaticamente a conexão dos nós clientes autorizados a partir do hash de credenciais recebido.
* **Como cientista de dados (operador do cliente),** quero utilizar uma interface gráfica (PyQt) para inserir minhas credenciais mockadas (o hash SHA-256 de autenticação é calculado automaticamente a partir delas), informar o endereço IP/porta do servidor central ao qual devo me conectar, selecionar a pasta local de imagens via seletor de diretórios e controlar o treinamento real (Iniciar/Parar) sem travamento da aplicação.
* **Como cientista de dados,** quero que o cliente use a mesma arquitetura CNN definida em `image-training.py`, carregue as imagens reais, normalize os pixels, persista o modelo treinado em formato Keras e envie os parâmetros e métricas ao servidor para agregação via FedAvg.
* **Como desenvolvedor/testador,** quero consultar um arquivo de referência separado contendo os dois pares de login/senha mockados, para não precisar vasculhar o código-fonte ao validar a autenticação em ambiente de teste.

### 1.3. Critérios de Aceitação
* Servidor e clientes devem ser executados em processos totalmente independentes, estabelecendo comunicação via protocolo IP.
* As interfaces gráficas de ambos os lados (Servidor e Cliente) devem ser desenvolvidas utilizando o framework PyQt (PyQt6).
* A interface do cliente deve dispor obrigatoriamente de: campos de login e senha, campo de endereço IP/porta do servidor central, Botão Iniciar, Botão Parar e seletor de diretório (`QFileDialog`). Não há campo de digitação manual de hash — ele é calculado automaticamente pela aplicação.
* A autenticação deve calcular, no cliente, um hash SHA-256 a partir do login e da senha informados (ex.: `SHA-256(login + ":" + senha)`) e enviá-lo como token no handshake gRPC; o servidor recalcula os hashes esperados a partir dos dois registros mockados que possui e só aceita a conexão se houver correspondência exata com um deles.
* A autenticação deve utilizar exatamente dois usuários mockados, cada um com login e senha predefinidos, mantidos em um arquivo de referência único (ex.: `mock_users.json`) importado tanto por `auth.py` do cliente quanto do servidor, para garantir que ambos os lados calculem os mesmos hashes esperados. Nenhum mock deve ser usado para imagens, amostras, pesos, métricas ou resultados do treinamento.
* O cliente deve carregar dados reais de uma pasta com subpastas por classe, redimensionar as imagens para `32x32`, convertê-las para RGB e normalizar os pixels para o intervalo `[0, 1]`, validando que a quantidade e os nomes das subpastas correspondam exatamente à lista fixa de classes definida em `model.py` antes de iniciar o treino.
* O treinamento local deve usar uma CNN TensorFlow/Keras compilada com `adam`, `sparse_categorical_crossentropy` e a métrica `accuracy`, seguindo `image-training.py`.
* A interrupção do treinamento via botão "Parar" deve ocorrer de forma coordenada (graceful) usando `threading.Event`, verificado a cada fim de lote/época por um `Callback` Keras dedicado que consulta o `Event` e define `model.stop_training = True` quando sinalizado, sem derrubar a interface gráfica do cliente.

### 1.4. Requisitos Funcionais

| ID | Categoria | Descrição do Requisito | Status |
| :--- | :--- | :--- | :--- |
| **RF-001** | Orquestração e Processos | Execução isolada do servidor central e dos clientes em processos separados, conectando-se via rede IP através do framework Flower.ai, utilizando a estratégia FedAvg para agregar os parâmetros do modelo real enviados por múltiplos clientes. | **Pendente** |
| **RF-002** | Autenticação e Hash SHA-256 | O cliente calcula automaticamente um hash SHA-256 a partir do login e senha mockados informados e o envia como token de handshake; o servidor recalcula os hashes esperados a partir do mesmo arquivo de referência de credenciais mockadas e rejeita a conexão se não houver correspondência exata. | **Pendente** |
| **RF-003** | Modelo e Dados Reais | Cada cliente deve construir a CNN Keras definida em `image-training.py`, carregar imagens reais de diretórios por classe, validar a lista de classes contra a constante fixa definida em `model.py`, normalizá-las e executar treinamento local com `model.fit`. | **Pendente** |
| **RF-004** | Interface do Servidor (PyQt) | Painel desktop para o operador do servidor definir porta/IP de escuta, iniciar o servidor e acompanhar a agregação federada (FedAvg) — sem necessidade de configurar hash manualmente. | **Pendente** |
| **RF-005** | Interface do Cliente (PyQt) | Janela desktop contendo campos de login e senha (o hash SHA-256 é derivado automaticamente deles), campo de endereço IP/porta do servidor central, seleção de diretório de imagens (`QFileDialog`), Botão Iniciar e Botão Parar. | **Pendente** |
| **RF-006** | Persistência e Métricas | Cada cliente registra loss e accuracy de treino/validação por época em `results.txt` local e envia essas mesmas métricas ao servidor junto com os parâmetros treinados; exibe a acurácia final na GUI. O servidor reconstrói o modelo Keras a partir dos parâmetros agregados por FedAvg ao final do treinamento federado e o salva em `cnn_model.keras`. | **Pendente** |
| **RF-007** | Credenciais Mockadas de Referência | Manter um arquivo de referência versionado (ex.: `mock_users.json`), separado do código-fonte, contendo os dois pares de login/senha mockados, sinalizado como uso exclusivo de ambiente de teste, para consulta rápida por desenvolvedores/testadores. | **Pendente** |

### 1.5. Requisitos Não-Funcionais
* **Isolamento de Threads:** A execução do ciclo do Flower (`start_client` / `start_server`) e do treinamento TensorFlow deve ser encapsulada em threads secundárias (`QThread`) para não bloquear o loop de eventos da interface gráfica PyQt.
* **Comunicação Inter-Processos:** A transferência de parâmetros e metadados de autenticação deve ocorrer via rede por gRPC/IP, utilizando interceptores para verificação do token SHA-256.
* **Compatibilidade do Modelo:** O modelo federado deve manter forma de entrada `(32, 32, 3)` e número de classes consistente entre os clientes e o servidor. O número e a ordem das classes são fixados como uma constante compartilhada (`NUM_CLASSES`/lista de classes) em `model.py` — nunca inferidos dinamicamente a partir do diretório local de cada cliente — garantindo que os pesos permaneçam compatíveis com a arquitetura compartilhada.
* **Dados Locais:** Os clientes devem aceitar diretórios contendo uma subpasta por classe e formatos de imagem suportados pelo carregador do Keras, sem fabricar amostras para completar o conjunto.
* **Portabilidade:** A aplicação deve ser compatível com ambientes desktop Windows e Linux executando Python 3.10+.
* **Isolamento de Ambiente:** Cada instância (cliente ou servidor) deve ser executada dentro de seu próprio ambiente virtual (`venv`), isolando as dependências de cada processo e evitando conflitos com pacotes instalados globalmente no sistema.

### 1.6. Casos Extremos
* **Credenciais/Hash Inválidos:** Como o hash SHA-256 é derivado diretamente do login e da senha, qualquer credencial que não corresponda a um dos dois registros mockados produz um hash que não bate com nenhum dos hashes esperados pelo servidor; nesse caso, a conexão gRPC deve ser rejeitada imediatamente, antes do início do treinamento local, com uma mensagem genérica de falha de autenticação, sem indicar qual campo está incorreto.
* **Diretório Inexistente ou Não Selecionado:** A tentativa de iniciar o treinamento sem selecionar uma pasta válida via `QFileDialog` deve exibir um alerta na GUI e barrar o início do processo.
* **Estrutura de Dados Inválida:** Diretórios sem subpastas de classe, sem imagens legíveis ou sem amostras suficientes devem interromper o início com uma mensagem de erro, sem criar dados artificiais.
* **Classes Incompatíveis:** Antes de iniciar o treino local, o cliente deve comparar a lista de subpastas encontradas no diretório selecionado com a lista fixa de classes definida em `model.py`; qualquer divergência de quantidade, nome ou ordem deve impedir o início do treinamento e exibir mensagem de erro na GUI, sem tentar adaptar ou completar as classes ausentes.
* **Falha no Treinamento:** Exceções do TensorFlow, carregamento de imagem ou persistência devem ser encaminhadas à GUI e encerrar apenas o worker, preservando a aplicação.
* **Cancelamento pelo Usuário:** O acionamento do botão "Parar" deve sinalizar a `threading.Event` de cancelamento; o `Callback` Keras verifica essa flag ao final do lote/época corrente, define `model.stop_training = True` e permite que `model.fit` retorne normalmente antes de encerrar o worker.

---

## Fase 2: Planejar

Esta fase descreve a arquitetura técnica e os componentes a serem desenvolvidos.

### 2.1. Visão Geral da Arquitetura

O sistema será estruturado nos seguintes módulos:

1. **Módulo de Autenticação e Utilidades (`auth.py`):**
   Carrega os dois registros mockados de login e senha a partir de um arquivo de referência único e versionado (`mock_users.json`, sinalizado como uso exclusivo de ambiente de teste), compartilhado entre cliente e servidor. Expõe a função `generate_auth_hash(login, senha) -> str`, que calcula `SHA-256(login + ":" + senha)` — usada pelo cliente para gerar o token enviado no handshake e pelo servidor para recalcular os hashes esperados a partir dos mesmos dois registros — e a respectiva rotina de comparação por igualdade. Nenhum outro dado da aplicação deve ser mockado.

2. **Módulo de Modelo e Dados (`model.py`, refatorado a partir do script de referência `image-training.py`):**
   `image-training.py` é o script original que define a arquitetura de referência da CNN; `model.py` é o módulo único, importado tanto pelo cliente quanto pelo servidor, que encapsula essa mesma arquitetura para uso em produção — não deve haver uma segunda definição divergente da CNN.
   - **`NUM_CLASSES`/`CLASS_NAMES`**: constante compartilhada, definida uma única vez em `model.py` e importada por cliente e servidor, fixando a quantidade e a ordem das classes da camada de saída. Não é inferida dinamicamente a partir do diretório de nenhum cliente.
   - **`create_cnn_model`/`build_model`**: CNN TensorFlow/Keras com entrada `(32, 32, 3)`, camadas convolucionais, pooling, `Flatten` e camadas densas dimensionadas por `NUM_CLASSES`, compilada para classificação multiclasse.
   - **Carregamento de dados**: imagens reais carregadas de diretórios por classe com `image_dataset_from_directory`, com validação prévia de que as subpastas encontradas correspondem a `CLASS_NAMES`, convertidas para NumPy, normalizadas por `255.0` e fornecidas ao treinamento local.
   - **`StopTrainingCallback`**: `tf.keras.callbacks.Callback` que consulta a `threading.Event` de cancelamento a cada fim de lote/época e define `model.stop_training = True` quando sinalizado, permitindo a interrupção graciosa do `model.fit`.
   - **Treinamento e persistência local**: execução de `model.fit` com o `StopTrainingCallback`, avaliação e registro, ao final de cada época, de loss/accuracy de treino e validação em `results.txt` local ao cliente.

3. **Servidor Central Desktop (`server_gui.py` e `server_logic.py`):**
   - **`ServerGUI`**: Interface PyQt6 para o operador do servidor definir a porta/IP de escuta, visualizar logs de conexões (incluindo tentativas de autenticação rejeitadas) e controlar o serviço. Não possui campo de hash — a validação é automática via `AggregationStrategy`.
   - **Autenticação via `AggregationStrategy.configure_fit`/`configure_evaluate`**: validado empiricamente que interceptar a autenticação em `ClientManager.register()` (chamando `client.get_properties()` a partir dali) trava para sempre nesta versão do Flower — `GrpcBridge.request()` espera, sem timeout, por uma resposta que só pode chegar depois que o próprio `register()` retornar, um deadlock estrutural do transporte gRPC bidirecional legado. Por isso a validação do hash (via `generate_auth_hash`, comparado aos dois registros de `mock_users.json`) acontece em `configure_fit`/`configure_evaluate`, o mesmo ponto em que o Flower já busca dados dos clientes — clientes não autorizados são removidos da lista antes de qualquer `FitIns`/`EvaluateIns` ser enviado, nunca treinam nem contribuem para a agregação. O `ClientManager` usado é o `SimpleClientManager` padrão do Flower.
   - **`FlowerServerWorker`**: `QThread` responsável por rodar o servidor Flower em segundo plano, via `server_logic.run_server`.
   - **`run_server`**: não chama `flwr.server.start_server` diretamente — essa função está deprecada nesta versão do Flower e registra signal handlers (`signal.signal`) incondicionalmente, o que levanta `ValueError` fora da thread principal (exatamente o caso do `FlowerServerWorker`/`QThread`). `run_server` reproduz apenas os passos internos necessários (`init_defaults`, `start_grpc_server`, `run_fl`), sem o registro de sinais.
   - **`AggregationStrategy`**: subclasse de `flwr.server.strategy.FedAvg` que fornece os parâmetros iniciais do modelo diretamente (construídos via `create_cnn_model`, sem depender de nenhum cliente), agrega por média federada os parâmetros dos clientes autorizados e, ao final da última rodada, instancia a CNN via `create_cnn_model` (com o mesmo `NUM_CLASSES` de `model.py`), aplica os pesos agregados via `model.set_weights` e salva o resultado em `cnn_model.keras` — este é o único ponto que persiste o modelo global.

4. **Lógica do Cliente (`client_logic.py`):**
   - **`FlowerNumPyClient`**: Subclasse de `flwr.client.NumPyClient` que instancia a CNN real, carrega o conjunto local de imagens (validando as classes contra `CLASS_NAMES`), implementa `get_parameters`, `fit` (usando `StopTrainingCallback`) e `evaluate`, emite métricas e checa eventos de cancelamento.

5. **Interface Gráfica do Cliente (`client_gui.py`):**
   - Interface PyQt6 com formulário para login e senha (o hash SHA-256 de autenticação é calculado internamente via `generate_auth_hash`, sem campo de digitação), campo de endereço IP/porta do servidor central e seletor de pasta (`QFileDialog`).
   - Controles de execução (Botão Iniciar e Botão Parar).
   - **`FlowerClientWorker`**: `QThread` que executa a rotina do cliente Flower e repassa mensagens de status e progresso para a interface gráfica.

### 2.2. Pilha de Tecnologia
* **Linguagem:** Python 3.10+
* **Aprendizado de Máquina:** TensorFlow/Keras e NumPy
* **Framework Federado:** Flower.ai (`flwr`) e `grpcio`
* **Interface Gráfica:** PyQt6
* **Segurança/Criptografia:** Módulo nativo `hashlib`; credenciais mockadas mantidas em `mock_users.json` (uso exclusivo de teste)
* **Dados e Persistência:** Imagens em diretórios por classe, `Pillow`, `cnn_model.keras` e `results.txt`
* **Concorrência:** Módulos `threading` e `PyQt6.QtCore.QThread`
* **Gerenciamento de Ambiente:** `venv` (módulo nativo do Python) para isolar as dependências de cada instância de cliente e do servidor

---

## Fase 3: Tarefas

Cronograma de implementação das funcionalidades com entrega prevista para 28/05/2026:

### Etapa 1 – Estrutura Base e Autenticação
* **[ ] Tarefa 1.1:** Configurar o ambiente virtual (`venv`) e instalar as dependências (`flwr`, `pyqt6`, `grpcio`).
* **[ ] Tarefa 1.2:** Desenvolver o módulo `auth.py` com `generate_auth_hash(login, senha)` e rotina de comparação por igualdade contra os hashes recalculados a partir de `mock_users.json`.
* **[ ] Tarefa 1.3:** Garantir as dependências do treinamento real (`tensorflow`, `numpy`, `pillow` e `matplotlib`, quando gráficos forem utilizados).
* **[ ] Tarefa 1.4:** Definir em `model.py` a constante compartilhada `NUM_CLASSES`/`CLASS_NAMES` usada por cliente e servidor para dimensionar a CNN e validar diretórios de imagens.
* **[ ] Tarefa 1.5:** Criar o arquivo de referência `mock_users.json` com os dois pares de login/senha mockados, versionado e documentado como uso exclusivo de ambiente de teste.

### Etapa 2 – Desenvolvimento do Servidor Central
* **[ ] Tarefa 2.1:** Implementar o interceptor gRPC que recalcula os hashes esperados a partir de `mock_users.json` e valida o hash recebido nos metadados do cliente.
* **[ ] Tarefa 2.2:** Desenvolver a interface gráfica do servidor (`server_gui.py`) em PyQt6, com campos para porta/IP de escuta e exibição do status do servidor.
* **[ ] Tarefa 2.3:** Encapsular a inicialização do servidor Flower em uma `QThread` integrada à GUI do servidor.
* **[ ] Tarefa 2.4:** Implementar a `AggregationStrategy` (subclasse de `FedAvg`) que reconstrói a CNN a partir dos parâmetros agregados na rodada final e persiste o resultado em `cnn_model.keras`.

### Etapa 3 – Desenvolvimento do Cliente e GUI
* **[ ] Tarefa 3.1:** Desenvolver a classe `FlowerNumPyClient` em `client_logic.py`, integrando a CNN real, o carregamento e validação das imagens por classe, `model.fit` com `StopTrainingCallback`, métricas e suporte a `threading.Event` para interrupção.
* **[ ] Tarefa 3.2:** Construir a interface gráfica do cliente (`client_gui.py`) em PyQt6 contendo:
  * Campos para login e senha (o hash SHA-256 é calculado automaticamente a partir deles ao iniciar).
  * Campo de endereço IP/porta do servidor central.
  * Componente `QFileDialog` para escolha do diretório local de imagens organizadas por classe.
  * Botão "Iniciar Treinamento".
  * Botão "Parar Treinamento".
* **[ ] Tarefa 3.3:** Criar a classe `FlowerClientWorker(QThread)` para rodar o cliente Flower sem congelar a interface.

### Etapa 4 – Testes e Validação Integrada
* **[ ] Tarefa 4.1:** Testar a execução em processos e janelas separadas comunicando-se via IP e agregando parâmetros da CNN real.
* **[ ] Tarefa 4.2:** Validar a rejeição de conexão quando login/senha não corresponderem a nenhum dos registros de `mock_users.json` (e, por consequência, o hash calculado não bater com nenhum hash esperado pelo servidor).
* **[ ] Tarefa 4.3:** Validar o carregamento de imagens reais, rejeição de diretórios com classes incompatíveis, normalização, treino local, avaliação e geração de `cnn_model.keras`/`results.txt`.
* **[ ] Tarefa 4.4:** Validar a interrupção graciosa do cliente pelo botão "Parar" (via `StopTrainingCallback`) durante o treino local ou a comunicação com o servidor.

---

## Fase 4: Próximos Passos (Backlog Futuro)

* **Evolução do Modelo:** Avaliar arquiteturas mais robustas, estratégias de agregação e particionamento dos dados após a validação do fluxo federado com a CNN real.