const canvas=document.getElementById("game"),ctx=canvas.getContext("2d");
const W=1280,H=720,GROUND=625,G=980,BALL_R=15,MAX_DRAG=300,ADVANCE_DELAY=1200,PREVIEW_HORIZON=80;
const ui={level:document.getElementById("level"),attempts:document.getElementById("attempts"),made:document.getElementById("made"),hp:document.getElementById("hp"),
angle:document.getElementById("angle"),power:document.getElementById("power"),spin:document.getElementById("spin"),
result:document.getElementById("result"),detail:document.getElementById("detail"),tip:document.getElementById("tip"),
distance:document.getElementById("labDistance"),apex:document.getElementById("labApex"),collision:document.getElementById("labCollision"),outcome:document.getElementById("labOutcome")};

const levels=[
 {name:"起点",hoop:{x:1080,y:365},obs:[]},
 {name:"弧高",hoop:{x:1080,y:365},obs:[{t:"bar",x:575,y:320,w:34,h:305}]},
 {name:"反弹",hoop:{x:1080,y:365},obs:[{t:"wall",x:700,y:300,w:34,h:270}]},
 {name:"通道",hoop:{x:1080,y:365},obs:[{t:"block",x:520,y:160,w:360,h:90},{t:"block",x:520,y:340,w:360,h:130},{t:"wall",x:880,y:0,w:34,h:250}]},
 {name:"时机",hoop:{x:1080,y:365},obs:[{t:"bar",x:640,y:350,w:34,h:145,move:true},{t:"wall",x:870,y:310,w:34,h:260}]}
];
let level=0,attempts=0,made=0,spin=0,drag=null,ball=null,preview=[],lastShot=null,lastTime=performance.now();
let node=1,hp=5,maxHp=5,shotsLeft=3,rimMul=1,ended=false,advanceTimer=null;

function nodeSpec(n){const li=(n-1)%5;return{levelIdx:li,elite:n===5,boss:n===10,
 rimMul:n===5?0.85:n===10?0.78:(n>=6?0.92:1)}}
function loadLevel(idx,mul){
 level=idx;rimMul=mul||1;shotsLeft=3;ball=null;drag=null;preview=[];lastShot=null;
 ui.result.textContent="准备出手";ui.detail.textContent="先观察障碍，再规划轨迹。";updateLab(null);draw();
}
function loadNode(n){
 node=n;const s=nodeSpec(n);
 loadLevel(s.levelIdx,s.rimMul);
 ui.level.textContent=n+"/10";ui.attempts.textContent=shotsLeft;ui.hp.textContent=hp;
 ui.tip.textContent=(s.boss?"BOSS · ":s.elite?"精英 · ":"")+"第 "+n+" 关 · "+current().name;
}
function startRun(){node=1;hp=maxHp;made=0;attempts=0;ended=false;
 document.getElementById("next").textContent="跳过此关";
 ui.made.textContent=0;loadNode(1)}
function endRun(msg){ended=true;ball=null;preview=[];
 ui.result.textContent="RUN OVER";ui.detail.textContent=msg+" —— 点「重开一局」再来";
 document.getElementById("next").textContent="重开一局"}
function ballStart(){return {x:145,y:GROUND-BALL_R,vx:0,vy:0,active:false,t:0,path:[],collisions:0}}
function current(){return levels[level]}
function boardRect(){const h=current().hoop;return{x:h.x+55,y:h.y-85,w:12,h:120}}

function pointer(e){const r=canvas.getBoundingClientRect();return{x:(e.clientX-r.left)*W/r.width,y:(e.clientY-r.top)*H/r.height}}
function getAim(p){
 const b=ball||ballStart(),dx=b.x-p.x,dy=b.y-p.y;
 const len=Math.min(MAX_DRAG,Math.hypot(dx,dy)); return {dx,dy,len,angle:Math.atan2(-dy,dx),power:len/MAX_DRAG}
}
function velocity(a,p){const speed=380+Math.pow(p,0.72)*980;return{vx:Math.cos(a)*speed,vy:-Math.sin(a)*speed}}

function simulate(v,steps=240){
 let s={x:145,y:GROUND-BALL_R,vx:v.vx,vy:v.vy},path=[],hits=0,apex=s.y,firstHit=null;
 for(let i=0;i<steps;i++){
   s.vy+=G/60;s.x+=s.vx/60;s.y+=s.vy/60;apex=Math.min(apex,s.y);
   if(s.y+BALL_R>GROUND){s.y=GROUND-BALL_R;s.vy*=-0.64;s.vx*=0.93;hits++}
   if(s.x-BALL_R<0){s.x=BALL_R;s.vx=Math.abs(s.vx)*0.72;hits++}
   if(s.x+BALL_R>W){s.x=W-BALL_R;s.vx=-Math.abs(s.vx)*0.72;hits++}
   for(const o of current().obs){
     const q=o.move?movingObstacle(o):o;if(circleRect(s,q)){
       resolveRect(s,q);hits++;
     }
   }
   const bd=boardRect();if(circleRect(s,bd)){resolveRect(s,bd);hits++}
   path.push({x:s.x,y:s.y});
   if(hits===1&&firstHit===null)firstHit=path.length-1;
   if(s.x>current().hoop.x+100||s.y>GROUND+100)break;
 }
 return{path,hits,apex,firstHit}
}
function movingObstacle(o){return {...o,y:o.y+Math.sin(performance.now()/700)*70}}
function circleRect(s,o){
 const cx=Math.max(o.x,Math.min(s.x,o.x+o.w)),cy=Math.max(o.y,Math.min(s.y,o.y+o.h));
 return (s.x-cx)**2+(s.y-cy)**2<BALL_R**2;
}
function resolveRect(s,o){
 const left=Math.abs((s.x+BALL_R)-o.x),right=Math.abs((o.x+o.w)-(s.x-BALL_R));
 const top=Math.abs((s.y+BALL_R)-o.y),bottom=Math.abs((o.y+o.h)-(s.y-BALL_R));
 const m=Math.min(left,right,top,bottom);
 if(m===left){s.x=o.x-BALL_R;s.vx=-Math.abs(s.vx)*0.78}
 else if(m===right){s.x=o.x+o.w+BALL_R;s.vx=Math.abs(s.vx)*0.78}
 else if(m===top){s.y=o.y-BALL_R;s.vy=-Math.abs(s.vy)*0.78}
 else{s.y=o.y+o.h+BALL_R;s.vy=Math.abs(s.vy)*0.78}
 s.vx+=spin*18
}
function hoopScore(s,prev){
 const h=current().hoop,rw=42*rimMul*0.81;
 const crossed=prev.y<h.y&&s.y>=h.y&&s.vy>0&&s.x>h.x-rw&&s.x<h.x+rw;
 return crossed;
}
function shoot(a,p){
 attempts++;shotsLeft--;ui.attempts.textContent=Math.max(0,shotsLeft);const v=velocity(a,p);ball={...ballStart(),vx:v.vx,vy:v.vy,active:true,path:[],collisions:0,t:0};
 lastShot={angle:a*180/Math.PI,power:p,spin};ui.angle.textContent=lastShot.angle.toFixed(1)+"°";ui.power.textContent=Math.round(p*100)+"%";ui.spin.textContent=spin.toFixed(1);
 const sim=simulate(v);preview=sim.path;updateLab(null);
 ui.result.textContent="出手！";ui.detail.textContent="观察篮球如何利用障碍改变轨迹。";
}
function finish(scored,reason){
 ball.active=false;ball=null;preview=[];
 if(scored)made++;
 ui.made.textContent=made;
 const s=nodeSpec(node);
 if(scored){
   hp=Math.min(maxHp,hp+1);ui.hp.textContent=hp;
   if(node===10){ended=true;ui.result.textContent="CHAMPION!";
     ui.detail.textContent="10 关全通——点「重开一局」再战。";
     document.getElementById("next").textContent="重开一局";}
   else{ui.result.textContent="SWISH!";ui.detail.textContent="进筐 +1 HP。";queueNext()}
 }else{
   const free=!s.elite&&!s.boss&&(3-shotsLeft===1);
   if(!free){hp--;ui.hp.textContent=hp}
   if(hp<=0){endRun("生命耗尽");return}
   if(shotsLeft<=0){
     if(s.boss){endRun("BOSS 三投未中");return}
     ui.result.textContent="SKIP";ui.detail.textContent="三次未中——跳过本关（无过关奖励）";
     queueNext();
   }else{
     ui.result.textContent="MISS";
     ui.detail.textContent=(free?"免费观察——":"失手 -1 HP——")+"本关还剩 "+shotsLeft+" 次。";
   }
 }
 if(lastShot){ui.angle.textContent=lastShot.angle.toFixed(1)+"°";ui.power.textContent=Math.round(lastShot.power*100)+"%";ui.spin.textContent=lastShot.spin.toFixed(1)}
 updateLab(lastShot?{...lastShot,scored}:null);
}
function queueNext(){
 if(advanceTimer)return;
 ui.tip.textContent="LEVEL CLEAR · 即将进入下一关";
 advanceTimer=setTimeout(()=>{advanceTimer=null;loadNode(node+1)},ADVANCE_DELAY);
}
function updateLab(s){
 ui.distance.textContent=s?((current().hoop.x-145)/100).toFixed(2)+" m":"—";
 ui.apex.textContent=s?( (GROUND-BALL_R - simulate(velocity(s.angle*Math.PI/180,s.power)).apex)/100).toFixed(2)+" m":"—";
 ui.collision.textContent=s?(preview.length?String(simulate(velocity(s.angle*Math.PI/180,s.power)).hits):"0")+" 次":"—";
 ui.outcome.textContent=s?(s.scored?"命中":"未命中"):"—";
}
function next(){
 if(advanceTimer){clearTimeout(advanceTimer);advanceTimer=null}
 if(ended){startRun();return}
 if(node>=10)return;
 loadNode(node+1);
}
function draw(){
 ctx.clearRect(0,0,W,H);drawBackground();drawCourt();drawHoop();drawObstacles();drawPlayer();
 if(!ball||!ball.active)drawPreview();
 else drawFlight();
 if(drag)drawAim(drag);
}
function drawBackground(){
 const g=ctx.createLinearGradient(0,0,0,H);g.addColorStop(0,"#182330");g.addColorStop(1,"#0d1218");ctx.fillStyle=g;ctx.fillRect(0,0,W,H);
 ctx.fillStyle="#202a32";for(let x=0;x<W;x+=80)ctx.fillRect(x,GROUND,78,H-GROUND);
 ctx.strokeStyle="#354351";ctx.lineWidth=2;for(let x=0;x<W;x+=80){ctx.beginPath();ctx.moveTo(x,GROUND);ctx.lineTo(x, H);ctx.stroke()}
 ctx.fillStyle="#71808c";ctx.font="14px monospace";ctx.fillText("2D PHYSICS COURT",24,52);
}
function drawCourt(){ctx.strokeStyle="#566572";ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(0,GROUND);ctx.lineTo(W,GROUND);ctx.stroke();ctx.fillStyle="#7b8994";ctx.font="12px monospace";ctx.fillText("START",118,GROUND+28)}
function drawHoop(){
 const h=current().hoop,rw=42*rimMul;ctx.strokeStyle="#dce5ec";ctx.lineWidth=7;ctx.beginPath();ctx.moveTo(h.x+55,h.y-85);ctx.lineTo(h.x+55,h.y+35);ctx.stroke();
 ctx.strokeStyle="#ff8d3a";ctx.lineWidth=6;ctx.beginPath();ctx.moveTo(h.x-rw,h.y,h.x+rw,h.y);ctx.stroke();
 ctx.strokeStyle="#d8e1e8";ctx.lineWidth=2;for(let i=-rw+7;i<=rw-7;i+=18){ctx.beginPath();ctx.moveTo(h.x+i,h.y+3);ctx.lineTo(h.x+i*.65,h.y+42);ctx.stroke()}ctx.beginPath();ctx.moveTo(h.x-rw*.57,h.y+42);ctx.lineTo(h.x+rw*.57,h.y+42);ctx.stroke();
}
function drawObstacles(){
 for(const o0 of current().obs){const o=o0.move?movingObstacle(o0):o0;ctx.fillStyle=o.t==="bar"?"#d89a4b":o.t==="wall"?"#53738e":"#657083";ctx.strokeStyle="#a9b8c5";ctx.lineWidth=2;ctx.fillRect(o.x,o.y,o.w,o.h);ctx.strokeRect(o.x,o.y,o.w,o.h);
   ctx.fillStyle="#dbe4eb";ctx.font="11px monospace";ctx.fillText(o.t==="bar"?"ARC":"BOUNCE",o.x+5,o.y+18);
 }
}
function drawPlayer(){
 const x=145,y=GROUND-18;ctx.strokeStyle="#f2a64a";ctx.lineWidth=7;ctx.lineCap="round";ctx.beginPath();ctx.arc(x,y-66,15,0,Math.PI*2);ctx.stroke();ctx.beginPath();ctx.moveTo(x,y-50);ctx.lineTo(x,y-12);ctx.moveTo(x,y-40);ctx.lineTo(x+24,y-62);ctx.moveTo(x,y-38);ctx.lineTo(x-22,y-20);ctx.moveTo(x,y-12);ctx.lineTo(x-18,y+5);ctx.moveTo(x,y-12);ctx.lineTo(x+19,y+4);ctx.stroke();
}
function drawAim(d){
 const b=ball||ballStart(),a=getAim(d),len=a.len;ctx.setLineDash([8,7]);ctx.strokeStyle="#79c8ff";ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(b.x,b.y);ctx.lineTo(b.x+Math.cos(a.angle)*len,b.y-Math.sin(a.angle)*len);ctx.stroke();ctx.setLineDash([]);
 ctx.fillStyle="#79c8ff";ctx.font="bold 14px monospace";ctx.fillText((a.angle*180/Math.PI).toFixed(1)+"°",b.x+15,b.y-18);
 ui.angle.textContent=(a.angle*180/Math.PI).toFixed(1)+"°";ui.power.textContent=Math.round(a.power*100)+"%";
 drawPreview(a.angle,a.power);
}
function drawPreview(a,p){
 if(a===undefined){if(!lastShot)return; a=lastShot.angle*Math.PI/180;p=lastShot.power}
 const sim=simulate(velocity(a,p));
 const cut=Math.min(sim.firstHit===null?sim.path.length:sim.firstHit,PREVIEW_HORIZON);
 ctx.fillStyle="#6fc1ff";for(let i=0;i<cut;i+=6){const q=sim.path[i];ctx.beginPath();ctx.arc(q.x,q.y,2.2,0,Math.PI*2);ctx.fill()}
}
function drawFlight(){
 const b=ball;if(b.path.length>2){ctx.strokeStyle="#ffca72";ctx.lineWidth=3;ctx.beginPath();b.path.forEach((q,i)=>i?ctx.lineTo(q.x,q.y):ctx.moveTo(q.x,q.y));ctx.stroke()}
 ctx.fillStyle="#e77b2d";ctx.beginPath();ctx.arc(b.x,b.y,BALL_R,0,Math.PI*2);ctx.fill();ctx.strokeStyle="#4d2b19";ctx.lineWidth=2;ctx.stroke();
 ctx.strokeStyle="#4d2b19";ctx.beginPath();ctx.arc(b.x,b.y,BALL_R*.65,0,Math.PI);ctx.stroke();
}
function tick(now){
 const dt=Math.min(.025,(now-lastTime)/1000);lastTime=now;
 if(ball?.active){
   const prev={x:ball.x,y:ball.y};ball.vy+=G*dt;ball.x+=ball.vx*dt;ball.y+=ball.vy*dt;ball.t+=dt;ball.path.push({x:ball.x,y:ball.y});
   if(ball.y+BALL_R>GROUND){ball.y=GROUND-BALL_R;ball.vy=-Math.abs(ball.vy)*.64;ball.vx*=.92;ball.collisions++}
   if(ball.x-BALL_R<0){ball.x=BALL_R;ball.vx=Math.abs(ball.vx)*.72;ball.collisions++}
   for(const o0 of current().obs){const o=o0.move?movingObstacle(o0):o0;if(circleRect(ball,o)){resolveRect(ball,o);ball.collisions++}}
   const bd=boardRect();if(circleRect(ball,bd)){resolveRect(ball,bd);ball.collisions++}
   if(hoopScore(ball,prev)){finish(true,"");}
   else if(ball.t>4.8||ball.y>GROUND+80||ball.x>W+80||ball.collisions>9)finish(false,"这条轨迹没有完成进筐。试试改变角度或力量。");
 }
 draw();requestAnimationFrame(tick)
}
canvas.addEventListener("pointerdown",e=>{if(ball?.active)return;drag=pointer(e);canvas.setPointerCapture(e.pointerId)});
canvas.addEventListener("pointermove",e=>{if(drag)drag=pointer(e)});
canvas.addEventListener("pointerup",e=>{if(!drag)return;const p=pointer(e),a=getAim(p);drag=null;if(a.len<18)return;shoot(a.angle,a.power)});
canvas.addEventListener("wheel",e=>{e.preventDefault();spin=Math.max(-8,Math.min(8,spin+(e.deltaY<0?.5:-.5)));ui.spin.textContent=spin.toFixed(1)},{passive:false});
document.getElementById("reset").onclick=startRun;document.getElementById("next").onclick=next;
startRun();requestAnimationFrame(tick);
if(typeof module!=="undefined")module.exports={levels,current,loadLevel,shoot,tick,next,hoopScore};