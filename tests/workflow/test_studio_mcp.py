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
from starlette.testclient import TestClient

from cadharness.workflow.benchmarks.cases import get_case
from cadharness.workflow.brief import read_json
from cadharness.workflow.runner import ROOT
from cadharness.studio.assistant import IDEAssistant
from cadharness.studio.jobs import Jobs
from cadharness.studio.server import create_app
from cadharness.studio.store import Store


class StudioMCPTests(unittest.TestCase):
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
