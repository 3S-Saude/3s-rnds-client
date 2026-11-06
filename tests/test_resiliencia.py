import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from rnds_client.base_client import RndsBaseClient
from rnds_client.auth import build_http_client
from rnds_client.settings import AuthMethod, RndsSettings


class ResilienciaTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancelamento_na_autenticacao_fecha_cliente(self):
        http = AsyncMock()
        with patch('rnds_client.base_client.RndsSettings.from_environment'), patch(
            'rnds_client.base_client.build_http_client', return_value=http
        ), patch.object(RndsBaseClient, '_ensure_access_token', side_effect=asyncio.CancelledError()):
            with self.assertRaises(asyncio.CancelledError):
                await RndsBaseClient.create()
        http.aclose.assert_awaited_once()

    async def test_tentativa_unica_sem_alterar_padrao(self):
        chamadas = []
        def responder(req):
            chamadas.append(req)
            return httpx.Response(503, request=req)
        cache = SimpleNamespace(load=AsyncMock(return_value=SimpleNamespace(value='token')))
        async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as http:
            client = RndsBaseClient(SimpleNamespace(cns_authorization=''), http, attempts=1, token_cache=cache)
            with self.assertRaises(httpx.HTTPStatusError):
                await client.request_with_retry('GET', 'https://teste.invalid/paciente')
        self.assertEqual(len(chamadas), 1)

    async def test_timeout_explicito_tambem_serve_para_autenticacao(self):
        settings = RndsSettings(auth_method=AuthMethod.API, auth_token_url='https://teste.invalid/token',
                                auth_login_url='https://teste.invalid/login', service_url='https://teste.invalid/api')
        timeout = httpx.Timeout(1, connect=0.5, pool=0.05)
        async with build_http_client(settings, timeout=timeout) as client:
            self.assertEqual(client.timeout, timeout)

    async def test_duas_instancias_compartilham_lock_de_autenticacao(self):
        lock = asyncio.Lock()
        dados = {}
        token = SimpleNamespace(value='novo')
        @asynccontextmanager
        async def bloquear():
            async with lock:
                yield
        async def load():
            return dados.get('token')
        async def save(value):
            dados['token'] = value
        async def autenticar(*args):
            await asyncio.sleep(0.02)
            return httpx.Response(200)
        cache = SimpleNamespace(load=load, save=save)
        clientes = [RndsBaseClient(None, AsyncMock(), token_cache=cache, token_lock=bloquear) for _ in range(2)]
        with patch.object(RndsBaseClient, '_authenticate', side_effect=autenticar) as autenticar_mock, patch(
            'rnds_client.base_client.AccessToken.from_response', return_value=token
        ):
            resultados = await asyncio.gather(*(c._ensure_access_token() for c in clientes))
        self.assertEqual(resultados, [token, token])
        self.assertEqual(autenticar_mock.await_count, 1)


class VersaoDistribuicaoTest(unittest.TestCase):
    def test_versao_publica_corresponde_a_distribuicao_instalada(self):
        from importlib.metadata import version
        import rnds_client
        self.assertEqual(rnds_client.__version__, version("3s-rnds-client"))
