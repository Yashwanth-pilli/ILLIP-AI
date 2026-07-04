// Self-contained HTML games — each a full standalone document (own JS, no
// external requests), rendered inside the sandboxed arcade iframe.

export const SNAKE = `<!doctype html><meta charset="utf-8">
<style>
  html,body{margin:0;height:100%;background:#0b0b16;color:#0ff;font-family:system-ui;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px}
  #hud{display:flex;gap:18px;font-weight:800;letter-spacing:1px;font-size:13px}
  #hud b{color:#f0f}
  canvas{background:#05050c;border:2px solid #0ff;border-radius:6px;box-shadow:0 0 26px #0ff5;touch-action:none}
  #o{position:fixed;inset:0;display:none;flex-direction:column;align-items:center;justify-content:center;background:#000a;font-size:22px;gap:6px}
  button{padding:8px 18px;background:#0ff;color:#000;border:0;border-radius:8px;font-weight:800;cursor:pointer}
  #hint{font-size:11px;color:#668}
</style>
<div id="hud"><span>SCORE <b id="sc">0</b></span><span>LEVEL <b id="lv">1</b></span><span>BEST <b id="bs">0</b></span></div>
<canvas id="c" width="360" height="360"></canvas>
<div id="hint">Arrow keys / swipe · walls wrap around · speed rises each level</div>
<div id="o"><div id="ot">Game Over</div><button onclick="reset()">Play again</button></div>
<script>
const c=document.getElementById('c'),x=c.getContext('2d'),G=18,N=c.width/G;
let snake,dir,ndir,food,score,level,best=0,timer,speed;
function rndFood(){let f;do{f={x:(Math.random()*N)|0,y:(Math.random()*N)|0}}while(snake.some(s=>s.x===f.x&&s.y===f.y));return f;}
function setSpeed(){speed=Math.max(55,120-(level-1)*10);clearInterval(timer);timer=setInterval(tick,speed);}
function reset(){snake=[{x:9,y:9},{x:8,y:9},{x:7,y:9}];dir={x:1,y:0};ndir=dir;food=rndFood();score=0;level=1;
  document.getElementById('o').style.display='none';upd();setSpeed();}
function upd(){document.getElementById('sc').textContent=score;document.getElementById('lv').textContent=level;document.getElementById('bs').textContent=best;}
function over(){best=Math.max(best,score);document.getElementById('ot').textContent='Game Over · Score '+score;document.getElementById('o').style.display='flex';clearInterval(timer);}
function tick(){
  dir=ndir;
  let h={x:snake[0].x+dir.x,y:snake[0].y+dir.y};
  h.x=(h.x+N)%N;h.y=(h.y+N)%N; // wrap
  if(snake.some(s=>s.x===h.x&&s.y===h.y)){over();return;}
  snake.unshift(h);
  if(h.x===food.x&&h.y===food.y){score++;if(score%5===0){level++;setSpeed();}food=rndFood();upd();}
  else snake.pop();
  x.fillStyle='#05050c';x.fillRect(0,0,c.width,c.height);
  x.fillStyle='#f0f';x.shadowColor='#f0f';x.shadowBlur=12;x.fillRect(food.x*G+3,food.y*G+3,G-6,G-6);
  x.shadowBlur=0;
  snake.forEach((s,i)=>{x.fillStyle=i===0?'#0ff':'#0aa';x.fillRect(s.x*G+1,s.y*G+1,G-2,G-2);});
}
addEventListener('keydown',e=>{const k=e.key;
  if(k==='ArrowUp'&&dir.y===0)ndir={x:0,y:-1};
  else if(k==='ArrowDown'&&dir.y===0)ndir={x:0,y:1};
  else if(k==='ArrowLeft'&&dir.x===0)ndir={x:-1,y:0};
  else if(k==='ArrowRight'&&dir.x===0)ndir={x:1,y:0};
  if(k.startsWith('Arrow'))e.preventDefault();
});
let tx,ty;
c.addEventListener('touchstart',e=>{tx=e.touches[0].clientX;ty=e.touches[0].clientY;},{passive:true});
c.addEventListener('touchend',e=>{const dx=e.changedTouches[0].clientX-tx,dy=e.changedTouches[0].clientY-ty;
  if(Math.abs(dx)>Math.abs(dy)){if(dx>0&&dir.x===0)ndir={x:1,y:0};else if(dx<0&&dir.x===0)ndir={x:-1,y:0};}
  else{if(dy>0&&dir.y===0)ndir={x:0,y:1};else if(dy<0&&dir.y===0)ndir={x:0,y:-1};}},{passive:true});
reset();
</script>`;

export const G2048 = `<!doctype html><meta charset="utf-8">
<style>
  html,body{margin:0;height:100%;background:#0b0b16;color:#eee;font-family:system-ui;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px}
  #hud{display:flex;gap:18px;font-weight:800;color:#a0f;font-size:14px}
  #g{display:grid;grid-template:repeat(4,64px)/repeat(4,64px);gap:8px;background:#1a1a2e;padding:8px;border-radius:12px;box-shadow:0 0 26px #a0f5;touch-action:none}
  .t{display:grid;place-items:center;border-radius:8px;font-weight:800;font-size:22px;background:#181830;color:#fff;transition:all .1s}
  #h{font-size:11px;color:#778}
  #ov{position:fixed;inset:0;display:none;flex-direction:column;align-items:center;justify-content:center;background:#000a;gap:8px;font-size:22px}
  button{padding:8px 18px;background:#a0f;color:#000;border:0;border-radius:8px;font-weight:800;cursor:pointer}
</style>
<div id="hud"><span>SCORE <span id="sc">0</span></span><span>BEST <span id="bs">0</span></span></div>
<div id="g"></div>
<div id="h">Arrow keys / swipe · reach 2048</div>
<div id="ov"><div id="ovt"></div><button onclick="reset()">New game</button></div>
<script>
const N=4;let b,score,best=0;const el=document.getElementById('g'),ss=document.getElementById('sc'),bb=document.getElementById('bs');
const COL={2:'#3a3a5a',4:'#4a4a7a',8:'#6a4aa0',16:'#8a4ac0',32:'#a04ad0',64:'#c04ae0',128:'#00b0b0',256:'#00c0a0',512:'#00d080',1024:'#e0c000',2048:'#ff00aa'};
function reset(){b=Array.from({length:N},()=>Array(N).fill(0));score=0;document.getElementById('ov').style.display='none';add();add();draw();}
function add(){const e=[];b.forEach((r,i)=>r.forEach((v,j)=>{if(!v)e.push([i,j])}));if(!e.length)return;const[i,j]=e[(Math.random()*e.length)|0];b[i][j]=Math.random()<0.9?2:4;}
function draw(){el.innerHTML='';ss.textContent=score;best=Math.max(best,score);bb.textContent=best;
  for(let i=0;i<N;i++)for(let j=0;j<N;j++){const v=b[i][j];const d=document.createElement('div');d.className='t';if(v){d.textContent=v;d.style.background=COL[v]||'#ff0088';d.style.boxShadow='0 0 10px '+(COL[v]||'#ff0088')+'66';}el.appendChild(d);}
  if(b.some(r=>r.includes(2048))){document.getElementById('ovt').textContent='You win! 🎉';document.getElementById('ov').style.display='flex';}
  else if(!moves()){document.getElementById('ovt').textContent='Game Over · '+score;document.getElementById('ov').style.display='flex';}}
function moves(){for(let i=0;i<N;i++)for(let j=0;j<N;j++){if(!b[i][j])return true;if(j<N-1&&b[i][j]===b[i][j+1])return true;if(i<N-1&&b[i][j]===b[i+1][j])return true;}return false;}
function slide(row){let a=row.filter(v=>v);for(let i=0;i<a.length-1;i++){if(a[i]===a[i+1]){a[i]*=2;score+=a[i];a[i+1]=0;}}a=a.filter(v=>v);while(a.length<N)a.push(0);return a;}
function rot(m){const r=Array.from({length:N},()=>Array(N).fill(0));for(let i=0;i<N;i++)for(let j=0;j<N;j++)r[j][N-1-i]=m[i][j];return r;}
function move(dir){let m=b.map(r=>r.slice());for(let k=0;k<dir;k++)m=rot(m);m=m.map(slide);for(let k=0;k<(4-dir)%4;k++)m=rot(m);
  if(JSON.stringify(m)!==JSON.stringify(b)){b=m;add();draw();}}
addEventListener('keydown',e=>{const d={ArrowLeft:0,ArrowUp:1,ArrowRight:2,ArrowDown:3}[e.key];if(d!==undefined){e.preventDefault();move(d);}});
let tx,ty;const g=document.getElementById('g');
g.addEventListener('touchstart',e=>{tx=e.touches[0].clientX;ty=e.touches[0].clientY;},{passive:true});
g.addEventListener('touchend',e=>{const dx=e.changedTouches[0].clientX-tx,dy=e.changedTouches[0].clientY-ty;
  if(Math.max(Math.abs(dx),Math.abs(dy))<20)return;
  if(Math.abs(dx)>Math.abs(dy))move(dx>0?2:0);else move(dy>0?3:1);},{passive:true});
reset();
</script>`;

export const TICTAC = `<!doctype html><meta charset="utf-8">
<style>
  html,body{margin:0;height:100%;background:#0b0b16;color:#eee;font-family:system-ui;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px}
  #top{display:flex;gap:10px;align-items:center;font-size:13px;font-weight:700}
  select{background:#161630;color:#0ff;border:1px solid #0ff5;border-radius:6px;padding:4px 8px;font-weight:700}
  #sc{color:#a0f}
  #g{display:grid;grid-template:repeat(3,84px)/repeat(3,84px);gap:8px}
  .c{display:grid;place-items:center;font-size:44px;font-weight:800;background:#141430;border:1px solid #0ff3;border-radius:10px;cursor:pointer;transition:all .12s}
  .c:hover{background:#1c1c44;box-shadow:0 0 12px #0ff5}
  .c.x{color:#0ff}.c.o{color:#f0f}
  #msg{font-size:16px;font-weight:800;height:22px}
  button{padding:7px 16px;background:#0ff;color:#000;border:0;border-radius:8px;font-weight:800;cursor:pointer}
</style>
<div id="top">
  <span id="sc">You 0 · ILLIP 0 · Draw 0</span>
</div>
<div id="g"></div>
<div id="msg">Your turn (X) — good luck, I don't lose 😏</div>
<button onclick="newGame()">New round</button>
<script>
const el=document.getElementById('g'),msg=document.getElementById('msg');
let bd,over,wins={p:0,a:0,d:0};
function newGame(){bd=Array(9).fill('');over=false;msg.textContent='Your turn (X)';draw();}
function draw(){el.innerHTML='';bd.forEach((v,i)=>{const d=document.createElement('div');d.className='c'+(v==='X'?' x':v==='O'?' o':'');d.textContent=v;d.onclick=()=>play(i);el.appendChild(d);});}
function win(b){const L=[[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]];for(const[a,c,d]of L)if(b[a]&&b[a]===b[c]&&b[a]===b[d])return b[a];return b.includes('')?null:'D';}
function play(i){if(over||bd[i])return;bd[i]='X';draw();if(end())return;setTimeout(aiMove,220);}
function end(){const w=win(bd);if(w){over=true;if(w==='X'){wins.p++;msg.textContent='You win?! 🤯 Rematch!';}else if(w==='O'){wins.a++;msg.textContent='ILLIP wins 😎';}else{wins.d++;msg.textContent='Draw — respect.';}
  document.getElementById('sc').textContent='You '+wins.p+' · ILLIP '+wins.a+' · Draw '+wins.d;return true;}return false;}
function aiMove(){if(over)return;const m=best();bd[m]='O';draw();end();if(!over)msg.textContent='Your turn (X)';}
function best(){let s=-2,mv;for(let i=0;i<9;i++)if(!bd[i]){bd[i]='O';const v=mini(bd,false);bd[i]='';if(v>s){s=v;mv=i;}}return mv;}
function mini(b,max){const w=win(b);if(w==='O')return 1;if(w==='X')return -1;if(w==='D')return 0;
  let best=max?-2:2;for(let i=0;i<9;i++)if(!b[i]){b[i]=max?'O':'X';const v=mini(b,!max);b[i]='';best=max?Math.max(best,v):Math.min(best,v);}return best;}
newGame();
</script>`;

export const GAMES = [
  { id: 'snake',  name: '🐍 Neon Snake', html: SNAKE,  desc: 'Levels + speed. Walls wrap. Arrows or swipe.' },
  { id: '2048',   name: '🔢 2048',       html: G2048,  desc: 'Merge to 2048. Win/lose detection.' },
  { id: 'tictac', name: '⭕ Tic-Tac-Toe', html: TICTAC, desc: 'Beat ILLIP if you can — it plays perfect.' },
];
