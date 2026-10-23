"""Run manually against an active studio: uv run python tests/mcp_smoke.py."""
import asyncio
import json
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    params = StdioServerParameters(command=sys.executable, args=['-c','from voxel_mcp.agent import main; main()'])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            names={t.name for t in (await client.list_tools()).tools}
            assert {'get_model','edit_voxels','compare_views','get_voxel_slice','undo'} <= names
            result=await client.call_tool('get_model',{})
            assert not result.isError, result
            model=json.loads(result.content[0].text)
            comparison=await client.call_tool('compare_views',{})
            assert not comparison.isError, comparison
            assert any(c.type=='image' for c in comparison.content), comparison
            rendered=await client.call_tool('render_view',{'view':'front'})
            assert not rendered.isError and rendered.content[0].type=='image', rendered
            p=model['voxels'][0]
            edit=await client.call_tool('edit_voxels',{'revision':model['revision'],'edits':[{'x':p[0],'y':p[1],'z':p[2],'color':[255,0,255]}]})
            assert not edit.isError, edit
            revision=json.loads(edit.content[0].text)['revision']
            restored=await client.call_tool('undo',{'revision':revision})
            assert not restored.isError, restored
            final=await client.call_tool('get_model',{})
            assert json.loads(final.content[0].text)['voxels']==model['voxels']
            print('MCP handshake, tools, image comparison, edit and undo passed')

asyncio.run(main())
