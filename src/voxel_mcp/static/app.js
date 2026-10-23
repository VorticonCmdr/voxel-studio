const $=id=>document.getElementById(id);let state, yaw=.65, pitch=.4, zoom=1, busy=false, toastTimer, visibleFaces=[];
function toast(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,5000)}
async function api(path,body){const r=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});if(!r.ok){let e=await r.json().catch(()=>({detail:r.statusText}));throw Error(e.detail||'Request failed')}return r.json()}
async function refresh(){state=await api('/api/state');render()}
async function action(body){if(busy)return;busy=true;try{await api('/api/action',{...body,revision:state.revision});await refresh()}catch(e){toast(e.message);await refresh().catch(()=>{})}finally{busy=false}}
function render(){const n=state.size;$('dimensions').textContent=`${n} × ${n} × ${n}`;$('count').textContent=state.voxels.length.toLocaleString()+' voxels';$('size').value=n;$('layer').max=n-1;$('layer').value=Math.min(+$('layer').value,n-1);$('undo').disabled=!state.undo_count;$('references').replaceChildren();for(const [view,src]of Object.entries(state.targets)){const row=document.createElement('div');row.className='ref';const im=new Image();im.src=src;row.append(im,document.createTextNode(view));$('references').append(row)}$('comparisons').replaceChildren();for(const [view,score] of Object.entries(state.scores)){const card=document.createElement('div');card.className='compare';card.innerHTML=`<div class="compare-title"><span>${view}</span><b>${(score.silhouette_iou*100).toFixed(1)}% shape</b></div><div class="strip"></div><small>${score.mismatched_pixels} pixels differ · RGB error ${score.rgb_mae.toFixed(1)}</small>`;for(const src of [state.targets[view],state.renders[view]]){const im=new Image();im.src=src;card.querySelector('.strip').append(im)}const diff=new Image();const c=document.createElement('canvas');c.width=c.height=n;const ctx=c.getContext('2d');Promise.all([loadImage(state.targets[view]),loadImage(state.renders[view])]).then(([a,b])=>{ctx.drawImage(a,0,0);const aa=ctx.getImageData(0,0,n,n);ctx.clearRect(0,0,n,n);ctx.drawImage(b,0,0);const bb=ctx.getImageData(0,0,n,n);for(let i=0;i<aa.data.length;i+=4){const mismatch=aa.data.slice(i,i+4).some((v,j)=>v!==bb.data[i+j]);aa.data.set(mismatch?[255,77,120,255]:[0,0,0,0],i)}ctx.putImageData(aa,0,0);diff.src=c.toDataURL()});card.querySelector('.strip').append(diff);$('comparisons').append(card)}if(!Object.keys(state.scores).length)$('comparisons').textContent='Import reference views to compare your volume.';drawScene();drawSlice()}
function loadImage(src){return new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(Error('Could not read image'));im.src=src})}
function drawScene(){if(!state)return;const c=$('scene'),rect=c.getBoundingClientRect(),dpr=devicePixelRatio||1;c.width=rect.width*dpr;c.height=rect.height*dpr;const ctx=c.getContext('2d');ctx.scale(dpr,dpr);const w=rect.width,h=rect.height,n=state.size,scale=Math.min(w,h)/n*.58*zoom;const cy=Math.cos(yaw),sy=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch);function project(x,y,z){x-=n/2;y-=n/2;z-=n/2;const a=x*cy-z*sy,b=x*sy+z*cy;return [w/2+a*scale,h/2-(y*cp-b*sp)*scale,y*sp+b*cp]}
ctx.strokeStyle='#49605a35';ctx.lineWidth=1;for(let i=0;i<=n;i++){for(const seg of [[[i,0,0],[i,0,n]],[[0,0,i],[n,0,i]]]){const a=project(...seg[0]),b=project(...seg[1]);ctx.beginPath();ctx.moveTo(a[0],a[1]);ctx.lineTo(b[0],b[1]);ctx.stroke()}}
const occupied=new Set(state.voxels.map(v=>v.slice(0,3).join(',')));const sides=[{n:[1,0,0],p:[[1,0,0],[1,1,0],[1,1,1],[1,0,1]],light:.82},{n:[-1,0,0],p:[[0,0,0],[0,0,1],[0,1,1],[0,1,0]],light:.66},{n:[0,1,0],p:[[0,1,0],[0,1,1],[1,1,1],[1,1,0]],light:1},{n:[0,-1,0],p:[[0,0,0],[1,0,0],[1,0,1],[0,0,1]],light:.5},{n:[0,0,1],p:[[0,0,1],[1,0,1],[1,1,1],[0,1,1]],light:.93},{n:[0,0,-1],p:[[0,0,0],[0,1,0],[1,1,0],[1,0,0]],light:.75}];const faces=[];for(const v of state.voxels){for(const f of sides){if(f.n[0]*sy*cp+f.n[1]*sp+f.n[2]*cy*cp<=0)continue;if(occupied.has([v[0]+f.n[0],v[1]+f.n[1],v[2]+f.n[2]].join(',')))continue;const points=f.p.map(p=>project(v[0]+p[0],v[1]+p[1],v[2]+p[2]));faces.push({points,voxel:v.slice(0,3),axis:f.n.findIndex(value=>value!==0),depth:points.reduce((s,p)=>s+p[2],0)/4,color:`rgb(${v.slice(3).map(c=>Math.round(c*f.light)).join(',')})`})}}faces.sort((a,b)=>a.depth-b.depth);visibleFaces=faces;for(const f of faces){ctx.beginPath();f.points.forEach((p,i)=>i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));ctx.closePath();ctx.fillStyle=f.color;ctx.fill();ctx.strokeStyle=f.color;ctx.lineWidth=.4;ctx.stroke()}}
function xyz(col,row){const n=state.size,i=+$('layer').value;return $('axis').value==='z'?[col,n-1-row,i]:$('axis').value==='y'?[col,i,row]:[i,n-1-row,col]}
function drawSlice(){if(!state)return;const n=state.size,c=$('slice'),ctx=c.getContext('2d'),s=c.width/n;const map=new Map(state.voxels.map(v=>[v.slice(0,3).join(','),v.slice(3)]));$('layerValue').value=$('layer').value;$('sliceHelp').textContent=$('axis').value==='y'?'Columns: +X · Rows: +Z':'Columns: '+($('axis').value==='z'?'+X':'+Z')+' · Rows: −Y';for(let row=0;row<n;row++)for(let col=0;col<n;col++){const color=map.get(xyz(col,row).join(','));ctx.fillStyle=color?`rgb(${color})`:(row+col)%2?'#253235':'#202c2e';ctx.fillRect(col*s,row*s,s,s);ctx.strokeStyle='#10171966';ctx.strokeRect(col*s,row*s,s,s)}}
$('slice').onclick=e=>{if(!state)return;const r=e.target.getBoundingClientRect(),n=state.size,col=Math.min(n-1,Math.floor((e.clientX-r.left)/r.width*n)),row=Math.min(n-1,Math.floor((e.clientY-r.top)/r.height*n)),[x,y,z]=xyz(col,row);if($('mode').value==='pick'){const v=state.voxels.find(v=>v[0]===x&&v[1]===y&&v[2]===z);if(v)$('color').value='#'+v.slice(3).map(c=>c.toString(16).padStart(2,'0')).join('');return}const color=$('mode').value==='erase'?null:$('color').value.match(/\w\w/g).map(v=>parseInt(v,16));action({op:'edit',edits:[{x,y,z,color}]})};
// Hit-test the same exposed faces used by the renderer, frontmost first.
// Coordinates are CSS pixels, matching the projected vertices at every DPR/zoom.
function pickSlice(clientX,clientY){
    const rect=$('scene').getBoundingClientRect();
    const x=clientX-rect.left,y=clientY-rect.top;
    const face=visibleFaces.slice().reverse().find(({points})=>{
        let positive=false,negative=false;
        for(let i=0;i<points.length;i++){
            const a=points[i],b=points[(i+1)%points.length];
            const cross=(b[0]-a[0])*(y-a[1])-(b[1]-a[1])*(x-a[0]);
            if(cross>1e-7)positive=true;
            if(cross<-1e-7)negative=true;
        }
        return !(positive&&negative);
    });
    if(!face)return;
    $('axis').value='xyz'[face.axis];
    $('layer').value=face.voxel[face.axis];
    drawSlice();
    toast(`Selected ${'XYZ'[face.axis]} layer ${face.voxel[face.axis]}`);
}
let drag;const scene=$('scene');
scene.onpointerdown=e=>{
    if(e.ctrlKey||e.metaKey){
        e.preventDefault();
        drag=null;
        pickSlice(e.clientX,e.clientY);
        return;
    }
    if(e.button!==0)return;
    drag=[e.clientX,e.clientY];scene.setPointerCapture(e.pointerId);
};
// macOS maps Control-click to a context menu; keep it available for picking.
scene.oncontextmenu=e=>{if(e.ctrlKey||e.metaKey)e.preventDefault()};
scene.onpointermove=e=>{if(!drag)return;yaw+=(e.clientX-drag[0])*.01;pitch=Math.max(-1.3,Math.min(1.3,pitch+(e.clientY-drag[1])*.01));drag=[e.clientX,e.clientY];drawScene()};scene.onpointerup=scene.onpointercancel=()=>drag=null;scene.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(.4,Math.min(3,zoom*Math.exp(-e.deltaY*.001)));drawScene()},{passive:false});new ResizeObserver(drawScene).observe(scene);
$('axis').onchange=$('layer').oninput=drawSlice;$('undo').onclick=()=>action({op:'undo'});$('carve').onclick=()=>action({op:'carve'});$('new').onclick=()=>action({op:'new',size:+$('size').value});$('demo').onclick=()=>action({op:'demo'});$('clear').onclick=()=>action({op:'clear_references'});$('layout').onchange=()=>{$('sheetLabel').hidden=$('layout').value!=='sheet'};
$('load').onchange=async e=>{try{await action({op:'load',project:JSON.parse(await e.target.files[0].text())})}catch(err){toast(err.message)}e.target.value=''};
$('upload').onchange=async e=>{let url;try{const file=e.target.files[0];if(!file)return;url=URL.createObjectURL(file);const im=await loadImage(url),n=state.size,views={};if($('layout').value==='single'){if(im.width!==n||im.height!==n)throw Error(`Expected ${n} × ${n} pixels. Set grid size and choose New empty first.`);const c=document.createElement('canvas');c.width=c.height=n;c.getContext('2d').drawImage(im,0,0);views[$('view').value]=c.toDataURL()}else{if(im.width%n||im.height%n)throw Error('Sheet dimensions must be multiples of grid size');const names=$('order').value.split(',').map(s=>s.trim());if(names.length!==im.width/n*(im.height/n)||new Set(names).size!==names.length||names.some(s=>!['front','right','back','left','top','bottom'].includes(s)))throw Error('Provide one unique camera name per cell');names.forEach((name,i)=>{const c=document.createElement('canvas');c.width=c.height=n;c.getContext('2d').drawImage(im,(i%(im.width/n))*n,Math.floor(i/(im.width/n))*n,n,n,0,0,n,n);views[name]=c.toDataURL()})}await action({op:'import',views});toast('References imported. Reconstruct when ready.')}catch(err){toast(err.message)}finally{if(url)URL.revokeObjectURL(url);e.target.value=''}};
refresh().catch(e=>toast(e.message));setInterval(async()=>{if(busy||!state)return;try{const next=await api('/api/state');if(next.revision!==state.revision){state=next;render()}}catch{}},2500);
