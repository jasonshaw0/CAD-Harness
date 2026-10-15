"""Reproducible real-browser acceptance via Playwriter's private headless mode.

Requires Node/npx and Chrome for Testing (`npx -y playwriter@latest browser install`).
No extension installation, personal browser state, desktop access or model API.
Uses a new workspace each run; never points at a user's active Studio session.
"""

import argparse
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
SOURCE = '''from build123d import Align, BuildLine, Cylinder, Ellipse, GeomType, Line, Part, Plane, Pos, ThreePointArc, fillet, sweep
from cadharness import CADDocument, Component
DETAILS = False
def create_project():
    align = (Align.CENTER, Align.CENTER, Align.MIN)
    outer = Cylinder(45, 96, align=align)
    outer = fillet(outer.edges().filter_by(GeomType.CIRCLE), 2)
    if DETAILS:
        with BuildLine() as path:
            Line((43,0,74),(50,0,74))
            ThreePointArc((50,0,74),(75,0,49),(50,0,24))
            Line((50,0,24),(43,0,24))
        section = Plane(origin=(43,0,74), x_dir=(0,0,1), z_dir=(1,0,0)) * Ellipse(8,6)
        outer += sweep(section, path=path.wire(), is_frenet=False)
        roots = [e for e in outer.edges() if e.geom_type == GeomType.BSPLINE and e.bounding_box().min.X > 43 and e.bounding_box().max.X < 45.01]
        outer = fillet(roots,2)
    mug = Part(outer - Pos(0,0,6)*Cylinder(42,90,align=align)).clean()
    components = {'mug':Component('mug',mug,role='printable-part')}
    if DETAILS:
        components['saucer'] = Component('saucer', Pos(0,0,-8)*Cylinder(55,5,align=align),role='printable-part')
    return CADDocument(id='render-fixture',name='Rendering fixture',revision='1',components=components)
'''


def playwriter(directory, *args):
    command = ['npx', '-y', 'playwriter@latest', *map(str, args)]
    if os.name == 'nt':
        command = ['cmd', '/d', '/s', '/c', *command]
    result = subprocess.run(command, cwd=directory, capture_output=True, text=True, encoding='utf-8', timeout=60)
    if result.returncode or 'Error executing code:' in result.stdout:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout


async def exercise(directory):
    workspace = directory / 'workspace'
    params = StdioServerParameters(command=sys.executable, args=['-m', 'cadharness.mcp_server',
        '--root', str(directory), '--studio', '--studio-workspace', str(workspace), '--studio-port', '0'], cwd=str(directory))
    async with stdio_client(params) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            async def call(name, args=None):
                result = await session.call_tool(name, args or {})
                if result.is_error:
                    raise RuntimeError(str(result))
                return result
            async def data(name, args=None):
                return (await call(name, args)).structured_content
            design = (await data('studio_create_design', {'title': 'Rendering acceptance fixture'}))['design']
            turn = (await data('studio_start_turn', {'design_id': design['id'], 'instruction':
                'Build a 90 mm cylindrical mug, then refine its handle and show a separate saucer.'}))['turn']
            await data('studio_get_context', {'include_contract': True})
            brief = {'schema': 'designworkflow.brief', 'schema_version': '1', 'id': design['id'], 'revision': 1,
                'domain': 'general-mechanical', 'coordinate_frame': 'mm, Z up, mug base Z0',
                'printable_components': ['mug'], 'dimensions': {}, 'questions': [], 'assumptions': [],
                'physical_validation_gaps': ['Browser rendering test only'], 'requirements': [{
                    'id': 'body-diameter', 'description': 'Body diameter', 'mandatory': True,
                    'prompt_ref': 'fixture', 'evidence_kind': 'geometry-derived', 'unit': 'mm',
                    'criteria': {'expected': 90, 'absolute_tolerance': .001},
                    'binding': {'type': 'bbox', 'component': 'mug', 'axis': 'Y'}}]}
            manifest = '[project]\nid="render-fixture"\nname="Rendering fixture"\nentrypoint="project.py:create_project"\n'
            async def build(source, brief=None):
                args = {'turn_id': turn['id'], 'files': [{'path': 'project.py', 'content': source},
                        {'path': 'cadharness.toml', 'content': manifest}]}
                if brief:
                    args['brief'] = brief
                job = (await data('studio_submit_candidate', args))['job']
                for _ in range(300):
                    result = await data('studio_get_job', {'job_id': job['id']})
                    if result['job']['status'] not in {'queued', 'building'}:
                        if result['job']['status'] != 'ready':
                            raise RuntimeError(str(result))
                        return result
                    await anyio.sleep(.1)
                raise RuntimeError('Fixture build did not finish')
            await build(SOURCE, brief)
            # New user instruction changes printable intent before adding the saucer.
            turn = (await data('studio_start_turn', {'design_id': design['id'], 'instruction':
                'Add the rounded mug handle and a separate saucer; preserve the body diameter.'}))['turn']
            brief['revision'] = 2
            brief['printable_components'] = ['mug', 'saucer']
            await build(SOURCE.replace('DETAILS = False', 'DETAILS = True'), brief)
            assert not list(workspace.rglob('renders')), 'Build generated unsolicited images'
            before_reports = {str(p): p.read_bytes() for p in workspace.rglob('run.json')}
            status = await data('studio_status')
            (directory / 'browser-config.json').write_text(json.dumps({'url': status['viewer_url'],
                'artifacts': str(directory)}), encoding='utf-8')
            created = await anyio.to_thread.run_sync(lambda: playwriter(directory, 'session', 'new', '--browser', 'headless'))
            match = re.search(r'Session (\d+) created', created)
            if not match:
                raise RuntimeError(created)
            browser_session = match.group(1)
            def step():
                output = playwriter(directory, '-s', browser_session, '--timeout', '20000', '-f', ROOT / 'scripts/verify_studio_rendering.js')
                print(output.strip(), flush=True)
            try:
                for _ in range(3):
                    await anyio.to_thread.run_sync(step)
                results = []
                for name, options in [('body-history', {'revision_id': 'r001', 'view': 'iso'}),
                                      ('assembly', {'view': 'iso'}), ('interior', {'view': 'top', 'component_ids': ['mug']}),
                                      ('saucer-only', {'component_ids': ['saucer']}),
                                      ('handle-detail', {'component_ids': ['mug'], 'view': 'front',
                                                         'focus_bounds_mm': [[40,-10,14],[85,10,84]]})]:
                    result = await call('studio_render_view', {'design_id': design['id'], **options})
                    metadata = result.structured_content
                    if metadata['status'] != 'captured':
                        raise RuntimeError(str(metadata))
                    image, = [c for c in result.content if c.type == 'image']
                    content = base64.b64decode(image.data)
                    assert sha256(content).hexdigest() == metadata['artifact']['sha256']
                    (directory / f'{name}.png').write_bytes(content)
                    results.append({"name": name, **metadata})
                await anyio.to_thread.run_sync(step)
                await anyio.to_thread.run_sync(step)
                failed = await data('studio_render_view', {'design_id': design['id']})
                assert failed['status'] == 'unavailable' and 'WebGL' in failed['reason'], failed
                assert len(list(workspace.rglob('renders/*.png'))) == 5
                await anyio.to_thread.run_sync(step)
                await anyio.to_thread.run_sync(step)
                for _ in range(70):
                    if not (await data('studio_status'))['rendering']['available']:
                        break
                    await anyio.sleep(.1)
                unavailable = await data('studio_render_view', {'design_id': design['id']})
                assert unavailable['status'] == 'unavailable', unavailable
                assert before_reports == {str(p): p.read_bytes() for p in workspace.rglob('run.json')}
                assert not list(workspace.rglob('*.js')), 'Unexpected browser scripts in CAD evidence'
                (directory / 'acceptance.json').write_text(json.dumps({'passed': True, 'captures': results,
                    'closed_browser': unavailable, 'webgl_failure': failed,
                    'viewport_preserved': True, 'extension_required': False}, indent=2), encoding='utf-8')
                print('Studio rendering acceptance passed:', directory)
            finally:
                await anyio.to_thread.run_sync(lambda: playwriter(directory, 'session', 'delete', browser_session))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'runs' / f'rendering-acceptance-{time.time_ns()}')
    directory = parser.parse_args().output.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    anyio.run(exercise, directory)
