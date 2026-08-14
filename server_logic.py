"""Logica do servidor central: autenticacao dos clientes e agregacao federada via FedAvg.

Flower nao expoe, na API publica de start_server, um mecanismo para injetar um
grpc.ServerInterceptor bruto. A alternativa obvia -- validar o hash dentro de
ClientManager.register() -- e estruturalmente um deadlock nesta versao do flwr:
GrpcBridge.request() (usado por client_proxy.get_properties()) espera, sem
timeout, por uma resposta que so pode chegar quando o loop de streaming do
Join() comeca a bombear mensagens; e esse loop so comeca DEPOIS que register()
retorna. Chamar get_properties() de dentro de register() trava para sempre.

Por isso a autenticacao acontece em AggregationStrategy.configure_fit /
configure_evaluate, que rodam depois que o cliente ja esta registrado e seu
loop de streaming ja esta ativo -- o mesmo ponto em que o proprio Flower busca
os parametros iniciais de um cliente. Clientes nao autorizados sao removidos
da lista antes de qualquer FitIns/EvaluateIns ser enviado; nunca treinam nem
contribuem para a agregacao.
"""
import logging

import flwr as fl
from flwr.common import GetPropertiesIns, Parameters, ndarrays_to_parameters, parameters_to_ndarrays
from flwr.server.client_manager import SimpleClientManager
from flwr.server.client_proxy import ClientProxy
from flwr.server.server import init_defaults, run_fl
from flwr.server.strategy import FedAvg
from flwr.server.superlink.fleet.grpc_bidi.grpc_server import start_grpc_server
from flwr.supercore.address import parse_address
from flwr.supercore.grpc import GRPC_MAX_MESSAGE_LENGTH

from auth import expected_hashes
from model import NUM_CLASSES, create_cnn_model

logger = logging.getLogger(__name__)


class AggregationStrategy(FedAvg):
    """FedAvg que autentica clientes por rodada e, na ultima rodada, salva o modelo global."""

    def __init__(self, *args, num_rounds: int, model_output_path: str = "cnn_model.keras", **kwargs):
        super().__init__(*args, **kwargs)
        self.num_rounds = num_rounds
        self.model_output_path = model_output_path
        self._expected_hashes = expected_hashes()

    def _is_authorized(self, client: ClientProxy, server_round: int) -> bool:
        try:
            properties = client.get_properties(GetPropertiesIns(config={}), timeout=10, group_id=server_round)
            return properties.properties.get("auth_hash") in self._expected_hashes
        except Exception:
            logger.warning("Falha ao validar credenciais do cliente %s.", client.cid)
            return False

    def _filter_authorized(self, pairs, server_round: int):
        authorized = []
        for client, ins in pairs:
            if self._is_authorized(client, server_round):
                authorized.append((client, ins))
            else:
                logger.warning(
                    "Cliente %s nao autorizado; removido da rodada %s.", client.cid, server_round
                )
        return authorized

    def configure_fit(self, server_round, parameters, client_manager):
        pairs = super().configure_fit(server_round, parameters, client_manager)
        return self._filter_authorized(pairs, server_round)

    def configure_evaluate(self, server_round, parameters, client_manager):
        pairs = super().configure_evaluate(server_round, parameters, client_manager)
        return self._filter_authorized(pairs, server_round)

    def aggregate_fit(self, server_round, results, failures):
        aggregated_parameters, aggregated_metrics = super().aggregate_fit(server_round, results, failures)

        if aggregated_parameters is not None and server_round == self.num_rounds:
            self._persist_global_model(aggregated_parameters)

        return aggregated_parameters, aggregated_metrics

    def _persist_global_model(self, parameters: Parameters) -> None:
        weights = parameters_to_ndarrays(parameters)
        model = create_cnn_model(num_classes=NUM_CLASSES)
        model.set_weights(weights)
        model.save(self.model_output_path)
        logger.info("Modelo global salvo em %s", self.model_output_path)


def run_server(server_address: str, num_rounds: int = 3, min_clients: int = 2) -> fl.server.History:
    """Equivalente a flwr.server.start_server, mas sem registrar signal handlers.

    flwr.server.start_server() chama register_signal_handlers() incondicionalmente,
    o que levanta "signal only works in main thread of the main interpreter" quando
    executado fora da thread principal (aqui, dentro do FlowerServerWorker/QThread
    da GUI). Reproduzimos apenas os passos de start_server que de fato importam
    para nos: inicializar o servidor/estrategia, subir o gRPC e rodar as rodadas.
    """
    initial_model = create_cnn_model(num_classes=NUM_CLASSES)
    strategy = AggregationStrategy(
        num_rounds=num_rounds,
        min_fit_clients=min_clients,
        min_evaluate_clients=min_clients,
        min_available_clients=min_clients,
        initial_parameters=ndarrays_to_parameters(initial_model.get_weights()),
    )
    client_manager = SimpleClientManager()

    host, port, is_v6 = parse_address(server_address)
    address = f"[{host}]:{port}" if is_v6 else f"{host}:{port}"

    server, config = init_defaults(
        server=None,
        config=fl.server.ServerConfig(num_rounds=num_rounds),
        strategy=strategy,
        client_manager=client_manager,
    )
    grpc_server = start_grpc_server(
        client_manager=server.client_manager(),
        server_address=address,
        max_message_length=GRPC_MAX_MESSAGE_LENGTH,
    )
    try:
        return run_fl(server=server, config=config)
    finally:
        grpc_server.stop(grace=1)
