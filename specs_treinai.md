# Especificação Técnica Completa: Sistema de Treinamento Federado com Flower.ai

**Versão:** 3.0 (Integração com o modelo TensorFlow/Keras real)  
**Status:** Documento de Engenharia de Software  
**Metodologia:** Desenvolvimento Orientado por Especificações (SDD)  

---

## Fase 1: Especificar

Esta fase define as capacidades e as fronteiras do sistema do ponto de vista funcional e de qualidade, servindo como a única fonte da verdade para a implementação do treinamento federado com dados e modelo reais.

### 1.1. Resumo
O sistema consiste em uma aplicação desktop distribuída para treinamento federado orquestrada pelo framework Flower.ai. A arquitetura é composta por instâncias de cliente e um servidor central rodando em processos distintos, comunicando-se via rede por endereço IP/gRPC. Ao abrir a aplicação (servidor ou cliente), ela carrega a identidade NOSTR do usuário a partir de uma chave privada (`nsec`) lida de uma variável de ambiente (`TREINAI_NSEC`, via arquivo `.env` local) — uma alternativa mais simples ao login remoto via NIP-46 (Nostr Connect/bunker), adequada para uso em scripts locais e Codespaces, adotada por ora no lugar de depender de um signer remoto. A chave fica apenas em memória, no processo local. Devidamente carregada a identidade, o usuário declara o relay e o id de um grupo NIP-29 (grupo baseado em relay) ao qual passa a se associar; esse grupo é usado tanto para descoberta — o servidor publica nele o endereço IP/porta em que está escutando, e o cliente o lê de lá em vez de digitá-lo manualmente — quanto para autorização — apenas clientes cuja chave pública esteja atualmente associada ao grupo (adicionados por um admin) têm suas conexões aceitas pelo servidor no handshake gRPC, no lugar do antigo par login/senha mockado e seu hash SHA-256. Cada cliente treina localmente uma CNN real em TensorFlow/Keras usando imagens organizadas em subpastas por classe, grava as métricas de treino em `results.txt` local e envia os parâmetros aprendidos (junto com as mesmas métricas) ao servidor, que agrega as atualizações de múltiplos clientes por meio do algoritmo FedAvg e devolve o modelo global atualizado. Imagens, amostras, pesos, métricas e demais dados do treinamento devem ser reais; nenhum deles é mockado. O número e a identidade das classes de classificação são fixados centralmente (não inferidos por cliente) para garantir que a arquitetura do modelo seja idêntica em todos os participantes da agregação federada.

### 1.2. Histórias do Usuário
* **Como operador do servidor central,** quero que a aplicação carregue minha identidade NOSTR a partir de uma chave privada em variável de ambiente antes de abrir a interface do servidor, declarar o relay e o id do grupo NIP-29 ao qual pertenço, e então usar uma interface gráfica (PyQt) para definir a porta/IP de escuta, publicar esse endereço no grupo e inicializar o servidor, validando automaticamente a conexão dos nós clientes a partir de sua associação atual ao grupo.
* **Como cientista de dados (operador do cliente),** quero que a aplicação carregue minha identidade NOSTR a partir de uma chave privada em variável de ambiente antes de abrir a interface do cliente, declarar o relay e o id do grupo NIP-29 ao qual fui adicionado, buscar automaticamente o endereço IP/porta do servidor central publicado nesse grupo, selecionar a pasta local de imagens via seletor de diretórios e controlar o treinamento real (Iniciar/Parar) sem travamento da aplicação.
* **Como cientista de dados,** quero que o cliente use a mesma arquitetura CNN definida em `image-training.py`, carregue as imagens reais, normalize os pixels, persista o modelo treinado em formato Keras e envie os parâmetros e métricas ao servidor para agregação via FedAvg.

### 1.3. Critérios de Aceitação
* Servidor e clientes devem ser executados em processos totalmente independentes, estabelecendo comunicação via protocolo IP.
* As interfaces gráficas de ambos os lados (Servidor e Cliente) devem ser desenvolvidas utilizando o framework PyQt (PyQt6).
* Tanto a interface do servidor quanto a do cliente devem exigir, antes de qualquer outra tela, o carregamento da identidade NOSTR a partir da variável de ambiente `TREINAI_NSEC` (lida também de um arquivo `.env` local, não versionado); se a variável não estiver definida, a tela deve mostrar o erro e permitir tentar novamente sem reiniciar o app. Após a identidade carregada, ambas devem coletar o relay e o id do grupo NIP-29 declarados pelo usuário; no cliente, ao confirmar o grupo, o próprio diálogo já checa se a chave carregada está cadastrada nesse grupo (via `nostr_groups.check_membership`) e avisa se ainda não estiver, sem fechar a tela.
* A interface do cliente deve dispor obrigatoriamente de: campo de endereço IP/porta do servidor central (preenchível automaticamente via descoberta no grupo NIP-29, mas editável), Botão Iniciar, Botão Parar e seletor de diretório (`QFileDialog`). Não há campos de login/senha nem de digitação manual de hash.
* A autenticação do cliente perante o servidor no handshake gRPC é feita pela chave pública NOSTR derivada da `nsec` carregada (enviada em `get_properties`); o servidor aceita a conexão apenas se essa chave estiver atualmente associada (evento `kind:9000`, sem `kind:9001` mais recente) ao grupo NIP-29 declarado pelo operador do servidor.
* O servidor deve publicar, ao iniciar, o endereço IP/porta em que está escutando como um evento assinado localmente (com a chave carregada de `TREINAI_NSEC`) no grupo NIP-29 declarado, para que os clientes o descubram; nenhuma credencial mockada (login/senha, `mock_users.json`) é mais utilizada em nenhuma das pontas. Nenhum mock deve ser usado para imagens, amostras, pesos, métricas ou resultados do treinamento.
* A `nsec` nunca deve ser digitada em campo de GUI, logada ou persistida pela aplicação em qualquer arquivo além da variável de ambiente/`.env` (não versionado) definida pelo próprio usuário.
* O cliente deve carregar dados reais de uma pasta com subpastas por classe, redimensionar as imagens para `32x32`, convertê-las para RGB e normalizar os pixels para o intervalo `[0, 1]`, validando que a quantidade e os nomes das subpastas correspondam exatamente à lista fixa de classes definida em `model.py` antes de iniciar o treino.
* O treinamento local deve usar uma CNN TensorFlow/Keras compilada com `adam`, `sparse_categorical_crossentropy` e a métrica `accuracy`, seguindo `image-training.py`.
* A interrupção do treinamento via botão "Parar" deve ocorrer de forma coordenada (graceful) usando `threading.Event`, verificado a cada fim de lote/época por um `Callback` Keras dedicado que consulta o `Event` e define `model.stop_training = True` quando sinalizado, sem derrubar a interface gráfica do cliente.

### 1.4. Requisitos Funcionais

| ID | Categoria | Descrição do Requisito | Status |
| :--- | :--- | :--- | :--- |
| **RF-001** | Orquestração e Processos | Execução isolada do servidor central e dos clientes em processos separados, conectando-se via rede IP através do framework Flower.ai, utilizando a estratégia FedAvg para agregar os parâmetros do modelo real enviados por múltiplos clientes. | **Pendente** |
| **RF-002** | Identidade NOSTR (chave via ambiente) e Grupo (NIP-29) | Ao iniciar, tanto servidor quanto cliente carregam a identidade NOSTR a partir da `nsec` na variável de ambiente `TREINAI_NSEC` (via `.env`) e exigem a declaração de um relay + id de grupo NIP-29; o servidor publica seu endereço no grupo e só aceita, no handshake gRPC, clientes cuja chave pública NOSTR esteja atualmente associada a esse grupo. | **Pendente** |
| **RF-003** | Modelo e Dados Reais | Cada cliente deve construir a CNN Keras definida em `image-training.py`, carregar imagens reais de diretórios por classe, validar a lista de classes contra a constante fixa definida em `model.py`, normalizá-las e executar treinamento local com `model.fit`. | **Pendente** |
| **RF-004** | Interface do Servidor (PyQt) | Painel desktop para o operador do servidor, após a identidade NOSTR carregada, definir porta/IP de escuta, publicar esse endereço no grupo NIP-29 declarado, iniciar o servidor e acompanhar a agregação federada (FedAvg). | **Pendente** |
| **RF-005** | Interface do Cliente (PyQt) | Janela desktop, aberta após a identidade NOSTR carregada, contendo campo de endereço IP/porta do servidor central (preenchível via descoberta no grupo NIP-29, editável), seleção de diretório de imagens (`QFileDialog`), Botão Iniciar e Botão Parar. | **Pendente** |
| **RF-006** | Persistência e Métricas | Cada cliente registra loss e accuracy de treino/validação por época em `results.txt` local e envia essas mesmas métricas ao servidor junto com os parâmetros treinados; exibe a acurácia final na GUI. O servidor reconstrói o modelo Keras a partir dos parâmetros agregados por FedAvg ao final do treinamento federado e o salva em `cnn_model.keras`. | **Pendente** |
| **RF-007** | Descoberta de Servidor via Grupo NIP-29 | O servidor assina localmente (com a chave carregada de `TREINAI_NSEC`) e publica no grupo NIP-29 declarado um evento replaceable (kind `30078`, NIP-78) com seu endereço IP/porta atual; o cliente consulta esse mesmo grupo para descobrir automaticamente o endereço, sem digitação manual. | **Pendente** |

### 1.5. Requisitos Não-Funcionais
* **Isolamento de Threads:** A execução do ciclo do Flower (`start_client` / `start_server`) e do treinamento TensorFlow deve ser encapsulada em threads secundárias (`QThread`) para não bloquear o loop de eventos da interface gráfica PyQt.
* **Comunicação Inter-Processos:** A transferência de parâmetros e metadados de autenticação deve ocorrer via rede por gRPC/IP; a autorização de cada cliente é verificada contra a associação atual ao grupo NIP-29, mantida em segundo plano por uma assinatura ao relay (ver `nostr_groups.py`).
* **Compatibilidade do Modelo:** O modelo federado deve manter forma de entrada `(32, 32, 3)` e número de classes consistente entre os clientes e o servidor. O número e a ordem das classes são fixados como uma constante compartilhada (`NUM_CLASSES`/lista de classes) em `model.py` — nunca inferidos dinamicamente a partir do diretório local de cada cliente — garantindo que os pesos permaneçam compatíveis com a arquitetura compartilhada.
* **Dados Locais:** Os clientes devem aceitar diretórios contendo uma subpasta por classe e formatos de imagem suportados pelo carregador do Keras, sem fabricar amostras para completar o conjunto.
* **Portabilidade:** A aplicação deve ser compatível com ambientes desktop Windows e Linux executando Python 3.10+.
* **Isolamento de Ambiente:** Cada instância (cliente ou servidor) deve ser executada dentro de seu próprio ambiente virtual (`venv`), isolando as dependências de cada processo e evitando conflitos com pacotes instalados globalmente no sistema.

### 1.6. Casos Extremos
* **Cliente Não Associado ao Grupo:** Uma chave NOSTR que não esteja atualmente associada (via `kind:9000`) ao grupo NIP-29 declarado — por nunca ter sido adicionada ou por ter sido removida (`kind:9001`) — deve ser barrada de iniciar o treinamento na própria GUI do cliente, com uma mensagem de espera clara; caso mesmo assim tente se conectar, a conexão gRPC deve ser rejeitada no handshake pelo servidor, antes do início do treinamento local.
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

1. **Módulos de Identidade e Grupo NOSTR (`nostr_auth.py`, `nostr_groups.py`, `nostr_login_dialog.py`, `async_worker.py`):**
   - **`nostr_auth.py`**: carrega a identidade NOSTR a partir de uma chave privada (`nsec`, bech32 ou hex) lida da variável de ambiente `TREINAI_NSEC` (via `python-dotenv`, aceitando também um arquivo `.env` local não versionado) usando a biblioteca `nostr-sdk`. Expõe `load_identity_from_env(env_var) -> AppIdentity`. `AppIdentity` guarda o objeto `Keys` (usado diretamente como signer local, sem depender de bunker/relay de pareamento) e a chave pública (hex) do usuário — a identidade usada em toda a aplicação no lugar de login/senha mockados. Essa é uma alternativa deliberadamente mais simples ao NIP-46 (Nostr Connect), adotada por ora para uso em scripts locais/Codespaces; o NIP-46 pode ser reintroduzido depois como opção adicional sem mudar `nostr_groups.py` (que assina através de qualquer `AsyncNostrSigner`, `Keys` incluso).
   - **`nostr_groups.py`**: implementa as operações NIP-29 usadas pelo app — `publish_server_address`/`fetch_server_address` (o servidor assina e publica seu endereço IP/porta como um evento replaceable kind `30078`/NIP-78 tagueado com `h=<group_id>`; o cliente busca esse evento para descobrir o endereço), `check_membership` (consulta pontual se uma chave é membro atual do grupo, pelo mais recente entre `kind:9000`/`kind:9001`) e `watch_membership` (assinatura contínua ao grupo usada pelo servidor para manter, em memória, o conjunto de chaves atualmente autorizadas).
   - **`nostr_login_dialog.py`**: diálogo PyQt6 reutilizado por cliente e servidor — carrega a identidade de `TREINAI_NSEC` (com botão "Tentar novamente" caso a variável não esteja definida) seguido da declaração de relay + group id. Aceita `require_membership: bool`; quando `True` (usado pelo cliente), ao clicar em "Confirmar" o diálogo chama `nostr_groups.check_membership` antes de fechar, bloqueando com um aviso se a chave ainda não estiver cadastrada no grupo. O servidor usa `require_membership=False` (o operador não precisa ter um evento `kind:9000` próprio para publicar no grupo).
   - **`async_worker.py`**: ponte genérica entre as corrotinas assíncronas do `nostr-sdk` (usadas pelas operações de rede em `nostr_groups.py`) e o event loop do PyQt6 (roda uma corrotina numa `QThread` e devolve o resultado por sinais), no mesmo padrão dos demais workers da aplicação.

2. **Módulo de Modelo e Dados (`model.py`, refatorado a partir do script de referência `image-training.py`):**
   `image-training.py` é o script original que define a arquitetura de referência da CNN; `model.py` é o módulo único, importado tanto pelo cliente quanto pelo servidor, que encapsula essa mesma arquitetura para uso em produção — não deve haver uma segunda definição divergente da CNN.
   - **`NUM_CLASSES`/`CLASS_NAMES`**: constante compartilhada, definida uma única vez em `model.py` e importada por cliente e servidor, fixando a quantidade e a ordem das classes da camada de saída. Não é inferida dinamicamente a partir do diretório de nenhum cliente.
   - **`create_cnn_model`/`build_model`**: CNN TensorFlow/Keras com entrada `(32, 32, 3)`, camadas convolucionais, pooling, `Flatten` e camadas densas dimensionadas por `NUM_CLASSES`, compilada para classificação multiclasse.
   - **Carregamento de dados**: imagens reais carregadas de diretórios por classe com `image_dataset_from_directory`, com validação prévia de que as subpastas encontradas correspondem a `CLASS_NAMES`, convertidas para NumPy, normalizadas por `255.0` e fornecidas ao treinamento local.
   - **`StopTrainingCallback`**: `tf.keras.callbacks.Callback` que consulta a `threading.Event` de cancelamento a cada fim de lote/época e define `model.stop_training = True` quando sinalizado, permitindo a interrupção graciosa do `model.fit`.
   - **Treinamento e persistência local**: execução de `model.fit` com o `StopTrainingCallback`, avaliação e registro, ao final de cada época, de loss/accuracy de treino e validação em `results.txt` local ao cliente.

3. **Servidor Central Desktop (`server_gui.py` e `server_logic.py`):**
   - **`ServerGUI`**: abre o `NostrLoginDialog` (carrega a identidade de `TREINAI_NSEC` + declaração de relay/grupo) antes de exibir a janela principal, onde o operador define a porta/IP de escuta, visualiza logs de conexões (incluindo tentativas de autenticação rejeitadas) e controla o serviço. Ao clicar em "Iniciar Servidor", publica o endereço no grupo (`nostr_groups.publish_server_address`) e inicia um `MembershipWatcher`.
   - **`MembershipWatcher`**: `QThread` que mantém uma assinatura viva ao grupo NIP-29 (via `nostr_groups.watch_membership`) e expõe `is_authorized(pubkey_hex) -> bool` de forma síncrona e sem I/O, a partir do conjunto de chaves atualmente associadas ao grupo.
   - **Autenticação via `AggregationStrategy.configure_fit`/`configure_evaluate`**: validado empiricamente que interceptar a autenticação em `ClientManager.register()` (chamando `client.get_properties()` a partir dali) trava para sempre nesta versão do Flower — `GrpcBridge.request()` espera, sem timeout, por uma resposta que só pode chegar depois que o próprio `register()` retornar, um deadlock estrutural do transporte gRPC bidirecional legado. Por isso a validação (via `membership_watcher.is_authorized`, a partir da chave pública NOSTR recebida em `get_properties`) acontece em `configure_fit`/`configure_evaluate`, o mesmo ponto em que o Flower já busca dados dos clientes — clientes não autorizados são removidos da lista antes de qualquer `FitIns`/`EvaluateIns` ser enviado, nunca treinam nem contribuem para a agregação. O `ClientManager` usado é o `SimpleClientManager` padrão do Flower.
   - **`FlowerServerWorker`**: `QThread` responsável por rodar o servidor Flower em segundo plano, via `server_logic.run_server`.
   - **`run_server`**: não chama `flwr.server.start_server` diretamente — essa função está deprecada nesta versão do Flower e registra signal handlers (`signal.signal`) incondicionalmente, o que levanta `ValueError` fora da thread principal (exatamente o caso do `FlowerServerWorker`/`QThread`). `run_server` reproduz apenas os passos internos necessários (`init_defaults`, `start_grpc_server`, `run_fl`), sem o registro de sinais.
   - **`AggregationStrategy`**: subclasse de `flwr.server.strategy.FedAvg` que fornece os parâmetros iniciais do modelo diretamente (construídos via `create_cnn_model`, sem depender de nenhum cliente), agrega por média federada os parâmetros dos clientes autorizados e, ao final da última rodada, instancia a CNN via `create_cnn_model` (com o mesmo `NUM_CLASSES` de `model.py`), aplica os pesos agregados via `model.set_weights` e salva o resultado em `cnn_model.keras` — este é o único ponto que persiste o modelo global.

4. **Lógica do Cliente (`client_logic.py`):**
   - **`FlowerNumPyClient`**: Subclasse de `flwr.client.NumPyClient` que instancia a CNN real, carrega o conjunto local de imagens (validando as classes contra `CLASS_NAMES`), implementa `get_parameters`, `fit` (usando `StopTrainingCallback`) e `evaluate`, emite métricas e checa eventos de cancelamento.

5. **Interface Gráfica do Cliente (`client_gui.py`):**
   - Abre o `NostrLoginDialog(require_membership=True)` (carrega a identidade de `TREINAI_NSEC` + declaração de relay/grupo, já checando a associação ao grupo antes de fechar) antes de exibir a janela principal, que contém um botão "Buscar Servidor" (preenche o campo de endereço IP/porta via `nostr_groups.fetch_server_address`, mantido editável) e o seletor de pasta (`QFileDialog`).
   - Controles de execução (Botão Iniciar e Botão Parar); antes de iniciar, verifica de novo a associação atual ao grupo via `nostr_groups.check_membership` (a associação pode ter mudado desde o login).
   - **`FlowerClientWorker`**: `QThread` que executa a rotina do cliente Flower e repassa mensagens de status e progresso para a interface gráfica.

### 2.2. Pilha de Tecnologia
* **Linguagem:** Python 3.10+
* **Aprendizado de Máquina:** TensorFlow/Keras e NumPy
* **Framework Federado:** Flower.ai (`flwr`) e `grpcio`
* **Interface Gráfica:** PyQt6
* **Identidade e Autorização:** NOSTR — `nostr-sdk` (identidade via chave local carregada de variável de ambiente, por ora no lugar do NIP-46 Nostr Connect; NIP-29 para grupos baseados em relay usados na descoberta do servidor e na autorização de clientes); `python-dotenv` para carregar a `nsec` de um arquivo `.env` local não versionado
* **Dados e Persistência:** Imagens em diretórios por classe, `Pillow`, `cnn_model.keras` e `results.txt`
* **Concorrência:** Módulos `threading` e `PyQt6.QtCore.QThread`
* **Gerenciamento de Ambiente:** `venv` (módulo nativo do Python) para isolar as dependências de cada instância de cliente e do servidor

---

## Fase 3: Tarefas

Cronograma de implementação das funcionalidades com entrega prevista para 28/05/2026:

### Etapa 1 – Estrutura Base e Autenticação
* **[ ] Tarefa 1.1:** Configurar o ambiente virtual (`venv`) e instalar as dependências (`flwr`, `pyqt6`, `grpcio`, `nostr-sdk`, `python-dotenv`).
* **[ ] Tarefa 1.2:** Desenvolver o módulo `nostr_auth.py` com `load_identity_from_env(env_var)`, que lê a `nsec` de `TREINAI_NSEC` (via `.env`/`python-dotenv`) e usa `nostr-sdk` (`Keys.parse`) para obter a `AppIdentity` (chave local como signer + chave pública) do usuário. Criar `.env.example` documentando a variável, e adicionar `.env` ao `.gitignore`.
* **[ ] Tarefa 1.3:** Garantir as dependências do treinamento real (`tensorflow`, `numpy`, `pillow` e `matplotlib`, quando gráficos forem utilizados).
* **[ ] Tarefa 1.4:** Definir em `model.py` a constante compartilhada `NUM_CLASSES`/`CLASS_NAMES` usada por cliente e servidor para dimensionar a CNN e validar diretórios de imagens.
* **[ ] Tarefa 1.5:** Desenvolver o módulo `nostr_groups.py` (NIP-29) com `publish_server_address`/`fetch_server_address` (descoberta do endereço do servidor via evento kind `30078` tagueado `h=<group_id>`), `check_membership` e `watch_membership` (autorização por associação ao grupo).

### Etapa 2 – Desenvolvimento do Servidor Central
* **[ ] Tarefa 2.1:** Implementar o `MembershipWatcher` (`QThread` que usa `nostr_groups.watch_membership`) e integrá-lo à `AggregationStrategy`, que passa a autorizar cada cliente pela chave pública NOSTR recebida em `get_properties`, validada contra a associação atual ao grupo NIP-29.
* **[ ] Tarefa 2.2:** Desenvolver a interface gráfica do servidor (`server_gui.py`) em PyQt6, com campos para porta/IP de escuta e exibição do status do servidor.
* **[ ] Tarefa 2.3:** Encapsular a inicialização do servidor Flower em uma `QThread` integrada à GUI do servidor.
* **[ ] Tarefa 2.4:** Implementar a `AggregationStrategy` (subclasse de `FedAvg`) que reconstrói a CNN a partir dos parâmetros agregados na rodada final e persiste o resultado em `cnn_model.keras`.

### Etapa 3 – Desenvolvimento do Cliente e GUI
* **[ ] Tarefa 3.1:** Desenvolver a classe `FlowerNumPyClient` em `client_logic.py`, integrando a CNN real, o carregamento e validação das imagens por classe, `model.fit` com `StopTrainingCallback`, métricas e suporte a `threading.Event` para interrupção.
* **[ ] Tarefa 3.2:** Construir a interface gráfica do cliente (`client_gui.py`) em PyQt6 contendo:
  * Identidade NOSTR carregada de `TREINAI_NSEC` e declaração de relay/grupo NIP-29 via `NostrLoginDialog(require_membership=True)` (checa a associação ao grupo já na confirmação), exibidos antes da janela principal.
  * Campo de endereço IP/porta do servidor central, preenchível via botão "Buscar Servidor" (`nostr_groups.fetch_server_address`).
  * Componente `QFileDialog` para escolha do diretório local de imagens organizadas por classe.
  * Botão "Iniciar Treinamento" (verifica `nostr_groups.check_membership` antes de conectar).
  * Botão "Parar Treinamento".
* **[ ] Tarefa 3.3:** Criar a classe `FlowerClientWorker(QThread)` para rodar o cliente Flower sem congelar a interface.

### Etapa 4 – Testes e Validação Integrada
* **[ ] Tarefa 4.1:** Testar a execução em processos e janelas separadas comunicando-se via IP e agregando parâmetros da CNN real.
* **[ ] Tarefa 4.2:** Validar a rejeição de conexão de um cliente cuja chave pública NOSTR não esteja (ou não esteja mais) associada ao grupo NIP-29 declarado pelo servidor, tanto na GUI do cliente (bloqueio antes de conectar) quanto no handshake gRPC (via `MembershipWatcher.is_authorized`).
* **[ ] Tarefa 4.3:** Validar o carregamento de imagens reais, rejeição de diretórios com classes incompatíveis, normalização, treino local, avaliação e geração de `cnn_model.keras`/`results.txt`.
* **[ ] Tarefa 4.4:** Validar a interrupção graciosa do cliente pelo botão "Parar" (via `StopTrainingCallback`) durante o treino local ou a comunicação com o servidor.

---

## Fase 4: Próximos Passos (Backlog Futuro)

* **Evolução do Modelo:** Avaliar arquiteturas mais robustas, estratégias de agregação e particionamento dos dados após a validação do fluxo federado com a CNN real.