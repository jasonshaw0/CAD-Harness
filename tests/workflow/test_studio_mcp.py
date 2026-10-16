"""The IDE can author, repair, and display CAD through real stdio MCP."""

from copy import deepcopy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server import MCPServer
from starlette.testclient import TestClient
from starlette.responses import JSONResponse
from starlette.routing import Route

from cadharness.workflow.benchmarks.cases import get_case
from cadharness.workflow.brief import read_json
from cadharness.workflow.runner import ROOT
from cadharness.studio.assistant import IDEAssistant
from cadharness.studio.jobs import Jobs
from cadharness.studio.mcp import STUDIO_API_REVISION, StudioService, connect_studio, register_tools
from cadharness.studio.rendering import RENDER_PROTOCOL
from cadharness.studio.server import create_app
from cadharness.studio.store import Store


class StudioMCPTests(unittest.TestCase):
    def test_poll_defers_partial_report_until_job_is_terminal(self):
        with TemporaryDirectory() as directory:
            owner = StudioService(Path(directory) / 'studio', port=0, library_root=directory, trusted_roots=[directory])
            try:
                register_tools(MCPServer('owner'), owner)
                store = owner.app.state.store
                design = store.create('Report publication race')
                design['latest_revision'] = 'r001'
                store.put(design)
                revision = store.design_root(design['id']) / 'revisions/r001'
                revision.mkdir(parents=True)
                report_file = revision / 'run.json'
                report_file.write_text('{"coverage":[', encoding='utf-8')
                job = {'id': 'job-1234abcd', 'design_id': design['id'], 'revision': 'r001', 'status': 'building'}
                store.put_job(job)
                self.assertIsNone(owner.invoke('studio_get_job', {'job_id': job['id']})['report'])
                report = {'ready_for_review': False, 'outcome': 'needs-revision', 'coverage': []}
                report_file.write_text(json.dumps(report), encoding='utf-8')
                job['status'] = 'needs-revision'
                store.put_job(job)
                self.assertEqual(owner.invoke('studio_get_job', {'job_id': job['id']})['report'], report)
                # Corruption in a completed report remains an error, not a
                # successful empty result or a blind JSON retry.
                report_file.write_text('{"coverage":[', encoding='utf-8')
                with self.assertRaises(json.JSONDecodeError):
                    owner.invoke('studio_get_job', {'job_id': job['id']})
            finally:
                owner.close()

    def test_new_client_rejects_stale_owner_before_advertising_render_tools(self):
        with TemporaryDirectory() as directory:
            workspace = Path(directory) / 'studio'
            owner = StudioService(workspace, port=0, library_root=directory, trusted_roots=[directory])
            try:
                register_tools(MCPServer('owner'), owner)
                saved = owner.app.state.store.create('Preserve this design')
                port = int(owner.url.rsplit(':', 1)[1])
                current = {**owner.identity, 'ready': True, 'api_revision': STUDIO_API_REVISION,
                           'render_protocol': RENDER_PROTOCOL, 'tools': sorted(owner.handlers)}
                legacy = {**owner.identity, 'ready': True}
                for payload in (legacy, {**current, 'api_revision': 1},
                                {**current, 'render_protocol': 'unknown'},
                                {**current, 'tools': ['studio_status']}):
                    async def stale_identity(request):
                        return JSONResponse(payload)
                    owner.app.router.routes[0] = Route('/api/mcp/identity', stale_identity)
                    with self.subTest(payload=payload), self.assertRaisesRegex(
                            RuntimeError, 'older or incompatible.*image-capture API.*Restart'):
                        connect_studio(workspace, port=port, library_root=directory, trusted_roots=[directory])
                self.assertEqual(owner.app.state.store.get(saved['id'])['title'], 'Preserve this design')
                self.assertTrue(owner.thread.is_alive())
            finally:
                owner.close()

    def test_shared_studio_requires_matching_workspace_roots_and_session(self):
        with TemporaryDirectory() as directory:
            workspace = Path(directory) / 'studio'
            owner = StudioService(workspace, port=0, library_root=directory, trusted_roots=[directory])
            try:
                register_tools(MCPServer('owner'), owner)
                port = int(owner.url.rsplit(':', 1)[1])
                owner.app.state.store.put_job({'id': 'job-1234abcd', 'status': 'building'})
                remote = connect_studio(workspace, port=port, library_root=directory, trusted_roots=[directory])
                self.assertTrue(remote.remote)
                self.assertEqual(remote.invoke('studio_status', {})['viewer_url'], owner.url)
                # An idle owner restart rotates the HTTP token. Refreshing a
                # rejected request must neither lose the attachment nor replay
                # a mutation that already executed.
                remote.token = 'expired-owner-token'
                created = remote.invoke('studio_create_design', {'title':'After owner restart'})
                self.assertEqual(created['design']['title'], 'After owner restart')
                self.assertEqual(len(owner.app.state.store.listing()), 1)
                original_identity = remote.identity
                remote.identity = {**original_identity, 'trusted_roots': []}
                remote.token = 'expired-owner-token'
                with self.assertRaisesRegex(RuntimeError, 'different workspace, trust roots'):
                    remote.invoke('studio_create_design', {'title': 'Must not execute'})
                self.assertEqual(len(owner.app.state.store.listing()), 1)
                remote.identity = original_identity
                self.assertEqual(owner.app.state.store.job('job-1234abcd')['status'], 'building')
                for options in ({'workspace': Path(directory) / 'other', 'trusted_roots': [directory]},
                                {'workspace': workspace, 'trusted_roots': [workspace]}):
                    with self.assertRaisesRegex(RuntimeError, 'different workspace, trust roots'):
                        connect_studio(port=port, library_root=directory, **options)
                # Existing HTTP session and origin protection also apply to the bridge.
                with TestClient(owner.app) as client:
                    body = {'identity': owner.identity, 'tool': 'studio_list_designs', 'arguments': {}}
                    self.assertEqual(client.post('/api/mcp/call', json=body).status_code, 403)
                    token = client.get('/api/session').json()['token']
                    headers = {'X-Studio-Token': token}
                    altered = {**body, 'identity': {**owner.identity, 'trusted_roots': []}}
                    self.assertEqual(client.post('/api/mcp/call', json=altered, headers=headers).status_code, 403)
                    self.assertEqual(client.post('/api/mcp/call', json=body,
                                                headers={**headers, 'Origin': 'https://example.com'}).status_code, 403)
                    body['tool'] = 'not_a_studio_tool'
                    self.assertEqual(client.post('/api/mcp/call', json=body, headers=headers).status_code, 400)
                    body.update(tool='studio_create_design', arguments={})
                    self.assertEqual(client.post('/api/mcp/call', json=body, headers=headers).status_code, 400)
                owner.app.state.authorize(False)
                with self.assertRaisesRegex(ValueError, 'Enable a trusted local session'):
                    remote.invoke('studio_create_design', {'title': 'locked'})
                remote.close()
                self.assertTrue(owner.thread.is_alive())
            finally:
                owner.close()

    def test_real_stdio_second_client_shares_viewer_and_build_queue(self):
        with TemporaryDirectory() as directory:
            workspace = Path(directory) / 'studio'
            fixture = get_case('square-mount')
            template = ROOT / fixture['template']
            files = [{'path': p.name, 'content': p.read_text(encoding='utf-8')}
                     for p in template.iterdir() if p.suffix in {'.py', '.toml'}]

            async def exercise():
                args = ['-m', 'cadharness.mcp_server', '--root', directory, '--studio',
                        '--studio-workspace', str(workspace), '--studio-port']
                async def call(session, name, arguments=None):
                    result = await session.call_tool(name, arguments or {})
                    self.assertFalse(result.is_error, result)
                    return result.structured_content

                params = StdioServerParameters(command=sys.executable, args=args + ['0'], cwd=directory)
                async with stdio_client(params) as streams:
                    async with ClientSession(*streams) as first:
                        await first.initialize()
                        status = await call(first, 'studio_status')
                        port = status['viewer_url'].rsplit(':', 1)[1]
                        second_params = StdioServerParameters(command=sys.executable, args=args + [port], cwd=directory)
                        async with stdio_client(second_params) as second_streams:
                            async with ClientSession(*second_streams) as second:
                                await second.initialize()
                                first_tools = {t.name for t in (await first.list_tools()).tools}
                                second_tools = {t.name for t in (await second.list_tools()).tools}
                                self.assertEqual(first_tools, second_tools)
                                self.assertEqual(len(second_tools), 26)
                                self.assertEqual((await call(second, 'studio_status'))['viewer_url'], status['viewer_url'])
                                design = (await call(second, 'studio_create_design', {'title': 'Shared MCP regression'}))['design']
                                context = await call(first, 'studio_get_context', {'include_contract': True})
                                self.assertEqual(context['design']['id'], design['id'])
                                turn = (await call(first, 'studio_start_turn', {'design_id': design['id'],
                                                                             'instruction': fixture['prompt']}))['turn']
                                submitted = await call(second, 'studio_submit_candidate', {
                                    'turn_id': turn['id'], 'files': files, 'brief': fixture['brief']})
                                for _ in range(300):
                                    output = await call(first, 'studio_get_job', {'job_id': submitted['job']['id']})
                                    if output['job']['status'] not in {'queued', 'building'}:
                                        break
                                    await anyio.sleep(.1)
                                self.assertEqual(output['job']['status'], 'ready', output)
                                remote_context = await call(second, 'studio_get_context')
                                self.assertEqual(remote_context['displayed_revision'], 'r001')
                                self.assertTrue(remote_context['report']['ready_for_review'])
                                # Visual findings may refine a geometrically passing candidate
                                # without fabricating another user instruction or changing intent.
                                refined = deepcopy(files)
                                for file in refined:
                                    if file['path'] == 'project.py':
                                        file['content'] = '# Refinement after inspecting the retained build\n' + file['content']
                                refinement = await call(second, 'studio_submit_candidate', {
                                    'turn_id': turn['id'], 'files': refined})
                                for _ in range(300):
                                    correction = await call(first, 'studio_get_job', {'job_id': refinement['job']['id']})
                                    if correction['job']['status'] not in {'queued', 'building'}:
                                        break
                                    await anyio.sleep(.1)
                                self.assertEqual(correction['job']['status'], 'ready', correction)
                                self.assertEqual(correction['report']['brief_sha256'], output['report']['brief_sha256'])
                                error = await second.call_tool('studio_start_turn', {'design_id': 'missing', 'instruction': 'test'})
                                self.assertTrue(error.is_error)
                        # Closing an attached stdio client must leave the original owner alive.
                        self.assertEqual((await call(first, 'studio_status'))['viewer']['design_id'], design['id'])
                        self.assertEqual((await call(first, 'studio_get_context'))['displayed_revision'], 'r002')
            anyio.run(exercise)

    def test_mcp_mode_has_no_nested_cli_calls(self):
        with TemporaryDirectory() as directory, patch('cadharness.studio.server.cli_command') as cli:
            with TestClient(create_app(directory, designer="mcp")) as client:
                session = client.get('/api/session').json()
                self.assertEqual(session['designer'], 'mcp')
                self.assertFalse(session['codex_available'])
                cli.assert_not_called()
                headers = {'X-Studio-Token': session['token']}
                client.post('/api/session', json={'authorize': True}, headers=headers)
                response = client.post('/api/designs', json={'prompt': 'Generate a part'}, headers=headers)
                self.assertEqual(response.status_code, 400)
                self.assertIn('IDE assistant', response.json()['error'])
                self.assertFalse(client.get('/api/designs').json()['designs'])

    def test_new_user_turn_supersedes_old_turn_and_selection_round_trips(self):
        with TemporaryDirectory() as directory:
            store = Store(directory)
            ide = IDEAssistant(store, Jobs(store))
            design = ide.create('test')
            first = ide.start_turn(design['id'], 'First user instruction')['turn']
            ide.select(design['id'], ['plate'])
            self.assertEqual(ide.context()['selected_components'], ['plate'])
            second = ide.start_turn(design['id'], 'Second user instruction')
            self.assertEqual(second['context']['selected_components'], ['plate'])
            with self.assertRaisesRegex(ValueError, 'superseded'):
                ide.submit(first['id'], [], None, '', session_id='test')
            with self.assertRaises(ValueError):
                ide.turn_path('../outside')

    def test_real_stdio_create_failed_measurement_repair_followup_and_export(self):
        with TemporaryDirectory() as directory:
            workspace = Path(directory) / 'studio'
            fixture = get_case('square-mount')
            template = ROOT / fixture['template']
            files = [{'path': p.name, 'content': p.read_text(encoding='utf-8')}
                     for p in template.iterdir() if p.suffix in {'.py', '.toml'}]
            broken = deepcopy(files)
            for file in broken:
                file['content'] = file['content'].replace('modeled_hole_count: int = -1', 'modeled_hole_count: int = 3')

            async def exercise():
                params = StdioServerParameters(command=sys.executable, args=[
                    '-m', 'cadharness.mcp_server', '--root', str(workspace), '--studio',
                    '--studio-workspace', str(workspace), '--studio-port', '0'], cwd=directory)
                async with stdio_client(params) as streams:
                    async with ClientSession(*streams) as session:
                        await session.initialize()
                        names = {tool.name for tool in (await session.list_tools()).tools}
                        self.assertIn('studio_submit_candidate', names)
                        self.assertIn('measure_cad_project', names)
                        async def call(name, args=None, error=False):
                            result = await session.call_tool(name, args or {})
                            self.assertEqual(bool(result.is_error), error, result)
                            return result.structured_content if not error else result
                        status = await call('studio_status')
                        self.assertFalse(status['model_calls'])
                        design = (await call('studio_create_design', {'title': 'MCP integration'}))['design']
                        context = await call('studio_get_context', {'include_contract': True})
                        self.assertIn('minimum_mm', context['contract'])
                        turn = (await call('studio_start_turn', {'design_id': design['id'], 'instruction': fixture['prompt']}))['turn']
                        async def build(files, brief=None):
                            result = await call('studio_submit_candidate', {'turn_id': turn['id'], 'files': files,
                                                'brief': brief, 'summary': 'Native MCP source'})
                            for _ in range(200):
                                result = await call('studio_get_job', {'job_id': result['job']['id']})
                                if result['job']['status'] not in {'queued', 'building'}:
                                    return result
                                await anyio.sleep(.1)
                            self.fail('CAD job did not finish')
                        failed = await build(broken, fixture['brief'])
                        self.assertEqual(failed['job']['status'], 'needs-revision')
                        self.assertFalse(failed['report']['ready_for_review'])
                        altered = deepcopy(fixture['brief'])
                        altered['requirements'][0]['criteria']['expected'] = 999
                        await call('studio_submit_candidate', {'turn_id': turn['id'], 'files': files, 'brief': altered}, error=True)
                        repaired = await build(files)
                        self.assertEqual(repaired['job']['status'], 'ready', repaired)
                        self.assertEqual(repaired['report']['brief_sha256'], failed['report']['brief_sha256'])
                        self.assertEqual(repaired['displayed_revision'], 'r002')
                        await call('studio_submit_candidate', {'turn_id': turn['id'], 'files': files}, error=True)
                        # Another user turn gets a fresh brief revision and build budget.
                        turn = (await call('studio_start_turn', {'design_id': design['id'], 'instruction': 'Keep the dimensions; rebuild for this new instruction.'}))['turn']
                        followup = await build(files, fixture['brief'])
                        self.assertEqual(followup['job']['status'], 'ready')
                        self.assertNotEqual(followup['report']['brief_sha256'], repaired['report']['brief_sha256'])
                        export = await call('studio_export_design', {'design_id': design['id'], 'file_format': 'stl'})
                        for _ in range(200):
                            output = await call('studio_get_job', {'job_id': export['job']['id']})
                            if output['job']['status'] not in {'queued', 'exporting'}:
                                break
                            await anyio.sleep(.1)
                        self.assertEqual(output['job']['status'], 'ready', output)
                        self.assertEqual([name for name in output['artifacts'] if name.endswith('.stl')], ['plate-standard.stl'])
                        frozen = read_json(workspace / 'designs' / design['id'] / 'revisions/r003/run.json')
                        self.assertIsNone(frozen['reviewed_source'])
                        self.assertEqual(frozen['execution_authorization']['mode'], 'trusted-session')
            anyio.run(exercise)


if __name__ == '__main__':
    unittest.main()
